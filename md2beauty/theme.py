from __future__ import annotations

from typing import Dict, Any, Optional, Mapping, Literal
from pydantic import BaseModel, Field
from pydantic import ConfigDict
import json
import os

HexColor = str  # validated via field patterns
Length = str | float | int   # CSS length like 1in, 2.5cm, 30mm, 12pt, 24px, or bare number (inches)


class StyleProps(BaseModel):
	model_config = ConfigDict(extra='forbid', populate_by_name=True)

	# Common CSS-like properties we support across formats
	font_family: Optional[str] = Field(default=None, alias='font-family')
	font_size: Optional[Length] = Field(default=None, alias='font-size')
	font_weight: Optional[str | int] = Field(default=None, alias='font-weight')
	font_style: Optional[Literal['normal', 'italic']] = Field(default=None, alias='font-style')
	color: Optional[HexColor] = None
	fill: Optional[HexColor] = None
	background_color: Optional[HexColor] = Field(default=None, alias='background-color')
	line_height: Optional[Length] = Field(default=None, alias='line-height')

	def as_css_dict(self) -> Dict[str, Any]:
		d: Dict[str, Any] = {}
		if self.font_family is not None:
			d['font-family'] = self.font_family
		if self.font_size is not None:
			d['font-size'] = self.font_size
		if self.font_weight is not None:
			d['font-weight'] = self.font_weight
		if self.font_style is not None:
			d['font-style'] = self.font_style
		if self.color is not None:
			d['color'] = self.color
		if self.fill is not None:
			d['fill'] = self.fill
		if self.background_color is not None:
			d['background-color'] = self.background_color
		if self.line_height is not None:
			d['line-height'] = self.line_height
		return d


class PageMargins(BaseModel):
	top: Optional[Length] = None
	right: Optional[Length] = None
	bottom: Optional[Length] = None
	left: Optional[Length] = None


class PageSettings(BaseModel):
	# Common page presets (lowercase keys)
	# Supports ISO A-series, selected ISO B-series, and common NA sizes
	type: Optional[Literal[
		'a0','a1','a2','a3','a4','a5','a6',
		'b5','b4','b3','b2','b1','b0',
		'letter','legal','tabloid','ledger','executive'
	]] = None
	width: Optional[Length] = None
	height: Optional[Length] = None
	orientation: Optional[Literal['portrait', 'landscape']] = None
	margins: Optional[PageMargins] = None


class FormatConfig(BaseModel):
	styles: Dict[str, StyleProps] = Field(default_factory=dict)
	page: Optional[PageSettings] = None


class Theme(BaseModel):
	"""
	Represents a Markdown theme with CSS-like styles.

	Structure:
	- styles: base, format-agnostic style map keyed by logical selectors (e.g., 'h1', 'p', 'code', 'blockquote', 'table', 'mermaid')
	- formats: optional per-format overrides keyed by format name ('html', 'docx', 'pptx')
	- meta: optional metadata (name, version, etc.)
	"""

	styles: Dict[str, StyleProps] = Field(default_factory=dict)
	formats: Dict[str, FormatConfig] = Field(default_factory=dict)
	meta: Dict[str, Any] = Field(default_factory=dict)
	# Optional page settings (e.g., page type and margins)
	# Example:
	# page = {
	#   "type": "a4" | "letter",             # optional preset
	#   "width": "8.5in", "height": "11in",  # optional explicit size (overrides type)
	#   "orientation": "portrait" | "landscape",
	#   "margins": {"top": "1in", "bottom": "1in", "left": "1in", "right": "1in"}
	# }
	page: Optional[PageSettings] = None

	# ------------------------ Loaders ------------------------
	@classmethod
	def from_json_file(cls, path: str) -> "Theme":
		with open(path, "r", encoding="utf-8") as f:
			data = json.load(f)
		# Structured form if explicit keys present
		if isinstance(data, dict) and ("styles" in data or "formats" in data or "meta" in data or "page" in data):
			data = Theme._normalize_theme_input(data)
			return cls(**data)
		# Otherwise treat as flat selector map
		if isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
			return cls(styles={k: StyleProps(**v) for k, v in data.items()})
		raise ValueError("Invalid theme JSON structure")

	@classmethod
	def to_json_file(cls, theme: "Theme", path: str) -> None:
		with open(path, "w", encoding="utf-8") as f:
			json.dump(theme.model_dump(), f, ensure_ascii=False, indent=2)

	@classmethod
	def from_dict(cls, data: Mapping[str, Any]) -> "Theme":
		if "styles" in data or "formats" in data or "meta" in data or "page" in data:
			normalized = Theme._normalize_theme_input(dict(data))
			return cls(**normalized)  # pydantic will parse nested models
		if all(isinstance(v, dict) for v in data.values()):
			# treat as a flat selector map for styles
			return cls(styles={k: StyleProps(**v) for k, v in data.items()})
		raise ValueError("Invalid theme dict structure")

	@classmethod
	def from_named_theme(cls, name: str, themes_dir: Optional[str] = None) -> "Theme":
		"""
		Load a theme by name from the themes folder (default: ./themes).
		The name should be the filename without .json extension.
		"""
		themes_dir = themes_dir or os.path.join(os.path.dirname(__file__), "themes")
		filename = f"{name}.json"
		path = os.path.join(themes_dir, filename)
		if not os.path.isfile(path):
			raise FileNotFoundError(f"Theme file not found: {path}")
		return cls.from_json_file(path)

	@staticmethod
	def _normalize_theme_input(data: Dict[str, Any]) -> Dict[str, Any]:
		# Convert legacy formats structure: formats[fmt] = {selector: props} -> FormatConfig(styles=...)
		formats = data.get('formats')
		if isinstance(formats, dict):
			new_formats: Dict[str, Any] = {}
			for fmt_name, fmt_val in formats.items():
				if isinstance(fmt_val, dict) and ('styles' in fmt_val or 'page' in fmt_val):
					new_formats[fmt_name] = fmt_val
				elif isinstance(fmt_val, dict):
					# assume it's a selector->props map
					new_formats[fmt_name] = {'styles': fmt_val}
				else:
					new_formats[fmt_name] = fmt_val
			data['formats'] = new_formats
		# Convert styles dict values into StyleProps handled by pydantic automatically via field aliases
		return data

	# ------------------------ Queries ------------------------
	def get_style(self, selector: str, *, format: Optional[str] = None) -> Optional[StyleProps]:
		base = self.styles.get(selector)
		override: Optional[StyleProps] = None
		if format and format in self.formats:
			fmt = self.formats[format]
			override = fmt.styles.get(selector)
		if not base and not override:
			return None
		data: Dict[str, Any] = {}
		if base:
			data.update({k: v for k, v in base.model_dump(exclude_unset=True).items() if v is not None})
		if override:
			data.update({k: v for k, v in override.model_dump(exclude_unset=True).items() if v is not None})
		return StyleProps(**data)

	# ------------------------ Conversions ------------------------
	def to_css(self) -> str:
		"""
		Convert theme to CSS for HTML rendering.
		Honors base styles + 'html' overrides.
		"""
		html_fmt = self.formats.get("html")
		combined: Dict[str, StyleProps] = {}
		# Merge: base first, then html overrides
		for sel, props in self.styles.items():
			combined[sel] = props
		if html_fmt:
			for sel, props in html_fmt.styles.items():
				base = combined.get(sel)
				if base:
					data = base.model_dump(exclude_unset=True)
					data.update({k: v for k, v in props.model_dump(exclude_unset=True).items() if v is not None})
					combined[sel] = StyleProps(**data)
				else:
					combined[sel] = props

		css_blocks: list[str] = []
		for selector, props in combined.items():
			decls_dict = props.as_css_dict()
			if not decls_dict:
				continue
			decls = "; ".join(f"{k}: {v}" for k, v in decls_dict.items())
			css_blocks.append(f"{selector} {{ {decls} }}")
		return "\n".join(css_blocks)

	def to_docx_styles(self) -> Dict[str, Dict[str, Any]]:
		"""Map theme to python-docx default style names and properties.

		Returns a dict suitable for applying to a docx Document's styles later.
		Keys include: 'Normal', 'Heading 1'..'Heading 6', 'Quote', 'Code' (if present).
		"""
		m: Dict[str, Dict[str, Any]] = {}

		# Helpers
		def css_size_to_pt(val: Any, *, base_pt: float = 12.0) -> Optional[float]:
			if val is None:
				return None
			try:
				s = str(val).strip()
				if s.endswith("pt"):
					return float(s[:-2])
				if s.endswith("px"):
					return float(s[:-2]) * 0.75  # 1px ~= 0.75pt at 96dpi
				if s.endswith("em") or s.endswith("rem"):
					return float(s[:-2]) * base_pt
				if s.replace(".", "", 1).isdigit():
					return float(s)
			except Exception:
				return None
			return None

		def color_hex(val: Any) -> Optional[str]:
			if not val:
				return None
			s = str(val).strip()
			if s.startswith("#") and (len(s) in (4, 7)):
				return s
			return None

		def style_to_docx(src: StyleProps, *, default_size_pt=12.0) -> Dict[str, Any]:
			return {
				"font_name": src.font_family,
				"font_size_pt": css_size_to_pt(src.font_size, base_pt=default_size_pt),
				"bold": bool(src.font_weight in ("bold", 700, "700")),
				"italic": bool(src.font_style == "italic"),
				"color": color_hex(src.color) or color_hex(src.fill),
			}

		# Build base map
		heading_map = {
			"h1": "Heading 1",
			"h2": "Heading 2",
			"h3": "Heading 3",
			"h4": "Heading 4",
			"h5": "Heading 5",
			"h6": "Heading 6",
		}

		# Base paragraph
		if (p := self.get_style("p", format="docx")):
			m["Normal"] = style_to_docx(p)
		elif (p := self.get_style("p")):
			m["Normal"] = style_to_docx(p)

		for sel, style_name in heading_map.items():
			st = self.get_style(sel, format="docx") or self.get_style(sel)
			if st:
				m[style_name] = style_to_docx(st, default_size_pt=14.0)

		for key, style_name in (("blockquote", "Quote"), ("code", "Code")):
			st = self.get_style(key, format="docx") or self.get_style(key)
			if st:
				m[style_name] = style_to_docx(st)

		return m

	def to_pptx_styles(self) -> Dict[str, Dict[str, Any]]:
		"""Map theme to a simple PPTX style dictionary for later application.

		Keys: 'Title', 'Subtitle', 'Body', 'Code'
		"""
		m: Dict[str, Dict[str, Any]] = {}

		def css_size_to_pt(val: Any, *, base_pt: float = 18.0) -> Optional[float]:
			try:
				s = str(val).strip()
				if s.endswith("pt"):
					return float(s[:-2])
				if s.endswith("px"):
					return float(s[:-2]) * 0.75
				if s.endswith("em") or s.endswith("rem"):
					return float(s[:-2]) * base_pt
				if s.replace(".", "", 1).isdigit():
					return float(s)
			except Exception:
				return None
			return None

		def color_hex(val: Any) -> Optional[str]:
			if not val:
				return None
			s = str(val).strip()
			if s.startswith("#") and (len(s) in (4, 7)):
				return s
			return None

		def style_to_pptx(src: StyleProps, *, default_size_pt=18.0) -> Dict[str, Any]:
			return {
				"font_name": src.font_family,
				"font_size_pt": css_size_to_pt(src.font_size, base_pt=default_size_pt),
				"bold": bool(src.font_weight in ("bold", 700, "700")),
				"italic": bool(src.font_style == "italic"),
				"color": color_hex(src.color) or color_hex(src.fill),
			}

		title = self.get_style("h1", format="pptx") or self.get_style("h1")
		if title:
			m["Title"] = style_to_pptx(title, default_size_pt=32.0)
		subtitle = self.get_style("h2", format="pptx") or self.get_style("h2")
		if subtitle:
			m["Subtitle"] = style_to_pptx(subtitle, default_size_pt=24.0)
		body = self.get_style("p", format="pptx") or self.get_style("p")
		if body:
			m["Body"] = style_to_pptx(body, default_size_pt=18.0)
		code = self.get_style("code", format="pptx") or self.get_style("pre") or self.get_style("code")
		if code:
			m["Code"] = style_to_pptx(code, default_size_pt=14.0)

		return m

	# ------------------------ Serializer abstraction ------------------------
	def serialize(self, format_name: str, **options) -> Any:
		"""Serialize the theme into a target format.

		Supported format_name values: 'html' (returns CSS string), 'docx' (returns dict of style mappings),
		'pptx' (returns dict of style mappings). Additional options are format-specific.
		"""
		fmt = format_name.lower()
		if fmt in ("html", "css"):
			# options: minify: bool
			minify = bool(options.get("minify", False))
			css = self.to_css()
			if minify:
				css = "".join(line.strip() for line in css.splitlines())
			return css
		if fmt == "docx":
			return self.to_docx_styles()
		if fmt == "pptx":
			return self.to_pptx_styles()
		raise ValueError(f"Unsupported serialization format: {format_name}")

	# ------------------------ Application Helpers (best-effort) ------------------------
	def apply_to_docx(self, document: Any) -> None:
		"""Best-effort apply styles to a python-docx Document's default styles.
		Safe to call even if some styles are absent.
		"""
		try:
			from docx.shared import Pt, RGBColor, Inches, Mm
			import os
			from docx.enum.section import WD_ORIENT  # type: ignore
		except Exception:
			return

		# First, apply page settings if present
		try:
			# Merge base page with docx overrides (typed models)
			base_page = self.page
			docx_fmt = self.formats.get("docx")
			page_cfg = PageSettings()
			if base_page:
				page_cfg = PageSettings(**base_page.model_dump(exclude_unset=True))
			if docx_fmt and docx_fmt.page:
				ov = PageSettings(**docx_fmt.page.model_dump(exclude_unset=True))
				page_cfg = PageSettings(**{**page_cfg.model_dump(exclude_unset=True), **ov.model_dump(exclude_unset=True)})

			if any(page_cfg.model_dump(exclude_unset=True).values()):
				# Helpers
				def _to_inches(val: Any) -> Optional[float]:
					if val is None:
						return None
					s = str(val).strip().lower()
					try:
						if s.endswith("in"):
							return float(s[:-2])
						if s.endswith("cm"):
							return float(s[:-2]) / 2.54
						if s.endswith("mm"):
							return float(s[:-2]) / 25.4
						if s.endswith("pt"):
							return float(s[:-2]) / 72.0
						if s.endswith("px"):
							return float(s[:-2]) / 96.0
						# bare number -> inches
						return float(s)
					except Exception:
						return None

				ptype = str(page_cfg.type or "").strip().lower()
				orientation = str(page_cfg.orientation or "").strip().lower()  # portrait|landscape
				# Defaults from type (portrait values)
				width_in: Optional[float] = None
				height_in: Optional[float] = None

				# Portrait dimension map in inches
				PAGE_INCHES = {
					# ISO A series
					'a0': (46.81, 33.11),  # 1189 x 841 mm
					'a1': (33.11, 23.39),  # 841 x 594 mm
					'a2': (23.39, 16.54),  # 594 x 420 mm
					'a3': (16.54, 11.69),  # 420 x 297 mm
					'a4': (11.69, 8.27),   # 297 x 210 mm
					'a5': (8.27, 5.83),    # 210 x 148 mm
					'a6': (5.83, 4.13),    # 148 x 105 mm
					# ISO B series (selection)
					'b0': (55.67, 39.37),  # 1414 x 1000 mm
					'b1': (39.37, 27.83),  # 1000 x 707 mm
					'b2': (27.83, 19.69),  # 707 x 500 mm
					'b3': (19.69, 13.90),  # 500 x 353 mm
					'b4': (13.90, 9.84),   # 353 x 250 mm
					'b5': (9.84, 6.93),    # 250 x 176 mm
					# North American
					'letter': (11.0, 8.5),
					'legal': (14.0, 8.5),
					'tabloid': (17.0, 11.0),
					'ledger': (11.0, 17.0),  # portrait form of ledger is tall 11x17
					'executive': (10.5, 7.25),
				}

				if ptype in PAGE_INCHES:
					height_in, width_in = PAGE_INCHES[ptype]  # stored as (h, w) order

				# Explicit overrides
				if (w := _to_inches(page_cfg.width)) is not None:
					width_in = w
				if (h := _to_inches(page_cfg.height)) is not None:
					height_in = h

				for section in getattr(document, "sections", []):
					# Apply orientation first so we can swap dimensions if needed
					if orientation in ("landscape", "portrait"):
						try:
							section.orientation = WD_ORIENT.LANDSCAPE if orientation == "landscape" else WD_ORIENT.PORTRAIT
						except Exception:
							pass

					# Size
					if width_in and height_in:
						# Ensure width/height order matches orientation
						if orientation == "landscape" and width_in < height_in:
							width_in, height_in = height_in, width_in
						if orientation == "portrait" and width_in > height_in:
							width_in, height_in = height_in, width_in
						section.page_width = Inches(width_in)
						section.page_height = Inches(height_in)

					# Margins
					margins = page_cfg.margins or PageMargins()
					if (v := _to_inches(margins.top)) is not None:
						section.top_margin = Inches(v)
					if (v := _to_inches(margins.bottom)) is not None:
						section.bottom_margin = Inches(v)
					if (v := _to_inches(margins.left)) is not None:
						section.left_margin = Inches(v)
					if (v := _to_inches(margins.right)) is not None:
						section.right_margin = Inches(v)
		except Exception:
			# ignore page setting errors
			pass

		styles_map = self.to_docx_styles()
		styles = getattr(document, "styles", None)
		if styles is None:
			return

		for style_name, props in styles_map.items():
			style = styles.__getitem__(style_name) if style_name in [s.name for s in styles] else None
			if style is None:
				# Skip if style doesn't exist in the template.
				continue
			font = getattr(style, "font", None)
			if not font:
				continue
			if props.get("font_name"):
				font.name = props["font_name"]
			if (sz := props.get("font_size_pt")):
				font.size = Pt(sz)
			font.bold = props.get("bold") if props.get("bold") is not None else font.bold
			font.italic = props.get("italic") if props.get("italic") is not None else font.italic
			if (col := props.get("color")) and isinstance(col, str) and col.startswith("#"):
				try:
					hexv = col.lstrip('#')
					r, g, b = (int(hexv[i:i+2], 16) for i in (0, 2, 4))
					font.color.rgb = RGBColor(r, g, b)
				except Exception:
					pass

	def apply_to_pptx(self, presentation: Any) -> None:
		"""Best-effort apply styles to a python-pptx Presentation.
		This is limited by python-pptx API. Intended as a starting point.
		"""
		try:
			pptx_styles = self.to_pptx_styles()
			# Attempt to set default text styles on slide masters
			for slide_layout in presentation.slide_layouts:
				for shape in getattr(slide_layout, 'shapes', []):
					if not hasattr(shape, 'text_frame'):
						continue
					tf = shape.text_frame
					# Title-like shapes often flagged as title
					key = "Title" if getattr(shape, 'is_title', False) else "Body"
					props = pptx_styles.get(key)
					if not props:
						continue
					for paragraph in tf.paragraphs:
						for run in paragraph.runs:
							if props.get("font_name"):
								run.font.name = props["font_name"]
							if props.get("font_size_pt"):
								from docx.shared import Pt  # type: ignore
								run.font.size = Pt(props["font_size_pt"])  # reuse Pt for unit
							if props.get("color") and isinstance(props["color"], str) and props["color"].startswith('#'):
								hexv = props["color"].lstrip('#')
								r, g, b = (int(hexv[i:i+2], 16) for i in (0, 2, 4))
								run.font.color.rgb = r, g, b  # best-effort; pptx color objects differ
							if props.get("bold") is not None:
								run.font.bold = props["bold"]
							if props.get("italic") is not None:
								run.font.italic = props["italic"]
		except Exception:
			# Silently ignore if APIs are unavailable; application remains optional.
			return


