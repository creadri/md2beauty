# Code Highlight Showcase

A large collection of fenced code blocks using many common language identifiers to exercise syntax highlighting and converter performance.

## Index
- Bash / Shell
- PowerShell
- JavaScript
- TypeScript
- JSX / TSX
- Python
- Java
- C
- C++
- C#
- Go
- Rust
- Ruby
- PHP
- Swift
- Kotlin
- Scala
- Dart
- Objective-C
- Haskell
- Elixir
- Erlang
- OCaml
- Lua
- Perl
- Julia
- R
- MATLAB / Octave
- SQL
- GraphQL
- HTML
- XML
- JSON
- YAML
- TOML
- INI
- CSS / SCSS / Less
- Markdown
- Dockerfile
- Makefile
- CMake
- NGINX
- Apache Config
- Terraform (HCL)
- ProtoBuf
- Diff
- Assembly (NASM)

---

## Bash / Shell
```bash
#!/usr/bin/env bash
set -euo pipefail

name=${1:-world}
for i in {1..3}; do
  echo "[$i] hello, $name"
  sleep 0.1
done
```

## PowerShell
```powershell
param([string]$Name = "World")
1..3 | ForEach-Object { Write-Host "[$_] Hello, $Name" }
```

## JavaScript
```javascript
function greet(name = "world") {
  for (let i = 1; i <= 3; i++) {
    console.log(`[${i}] hello, ${name}`);
  }
}

const user = { id: 42, name: "Otter" };
const { id, name } = user;
greet(name);
```

## TypeScript
```ts
type User = { id: number; name: string };

function greet(user: User) {
  for (let i = 1; i <= 3; i++) console.log(`[${i}] hello, ${user.name}`);
}

const u: User = { id: 1, name: "Kaelen" };
greet(u);
```

## JSX
```jsx
export default function App() {
  return (
    <main>
      <h1>Hello, Otter!</h1>
    </main>
  );
}
```

## TSX
```tsx
type Props = { title: string };
const App = ({ title }: Props) => <h1>{title}</h1>;
export default App;
```

## Python
```python
def greet(name: str = "world") -> None:
    for i in range(1, 4):
        print(f"[{i}] hello, {name}")

if __name__ == "__main__":
    greet("Lutra")
```

## Java
```java
class Main {
  static void greet(String name) {
    for (int i = 1; i <= 3; i++) System.out.println("[" + i + "] hello, " + name);
  }
  public static void main(String[] args) { greet("River"); }
}
```

## C
```c
#include <stdio.h>
int main(void) {
  for (int i = 1; i <= 3; i++) printf("[%d] hello, %s\n", i, "Otter");
  return 0;
}
```

## C++
```cpp
#include <iostream>
int main(){
  for(int i=1;i<=3;i++) std::cout << "["<<i<<"] hello, Otter" << std::endl;
}
```

## C#
```csharp
using System;
class Program{
  static void Main(){ for(int i=1;i<=3;i++) Console.WriteLine($"[{i}] hello, Otter"); }
}
```

## Go
```go
package main
import "fmt"
func main(){
  for i:=1; i<=3; i++ { fmt.Printf("[%d] hello, Otter\n", i) }
}
```

## Rust
```rust
fn main() {
    for i in 1..=3 { println!("[{}] hello, Otter", i); }
}
```

## Ruby
```ruby
3.times { |i| puts "[#{i+1}] hello, Otter" }
```

## PHP
```php
<?php
for ($i=1; $i<=3; $i++) { echo "[$i] hello, Otter\n"; }
```

## Swift
```swift
for i in 1...3 { print("[\(i)] hello, Otter") }
```

## Kotlin
```kotlin
fun main(){ for(i in 1..3) println("[${'$'}i] hello, Otter") }
```

## Scala
```scala
object Main extends App { (1 to 3).foreach(i => println(s"[$i] hello, Otter")) }
```

## Dart
```dart
void main(){ for (var i=1; i<=3; i++) print('[${i}] hello, Otter'); }
```

## Objective-C
```objectivec
#import <Foundation/Foundation.h>
int main(){ @autoreleasepool { for(int i=1;i<=3;i++) NSLog(@"[%d] hello, Otter", i); } return 0; }
```

## Haskell
```haskell
main = mapM_ putStrLn ["[" ++ show i ++ "] hello, Otter" | i <- [1..3]]
```

## Elixir
```elixir
Enum.each(1..3, fn i -> IO.puts("[#{i}] hello, Otter") end)
```

## Erlang
```erlang
-module(main).
-export([start/0]).
start() -> lists:foreach(fun(I) -> io:format("[~p] hello, Otter~n", [I]) end, lists:seq(1,3)).
```

## OCaml
```ocaml
let () = for i = 1 to 3 do Printf.printf "[%d] hello, Otter\n" i done
```

## Lua
```lua
for i=1,3 do print(string.format("[%d] hello, Otter", i)) end
```

## Perl
```perl
for my $i (1..3) { print "[$i] hello, Otter\n"; }
```

## Julia
```julia
for i in 1:3
    println("[", i, "] hello, Otter")
end
```

## R
```r
for (i in 1:3) { cat(sprintf("[%d] hello, Otter\n", i)) }
```

## MATLAB / Octave
```matlab
for i = 1:3
  fprintf('[%d] hello, Otter\n', i);
end
```

## SQL
```sql
SELECT CONCAT('[', n, '] hello, Otter') AS greeting
FROM (SELECT 1 AS n UNION ALL SELECT 2 UNION ALL SELECT 3) t;
```

## GraphQL
```graphql
query Hello($times: Int!) {
  greetings(times: $times) { index message }
}
```

## HTML
```html
<!doctype html>
<html>
  <head><meta charset="utf-8"><title>Hello</title></head>
  <body><h1>Hello, Otter</h1></body>
</html>
```

## XML
```xml
<greetings>
  <greet index="1">hello, Otter</greet>
  <greet index="2">hello, Otter</greet>
  <greet index="3">hello, Otter</greet>
</greetings>
```

## JSON
```json
{
  "items": [
    { "index": 1, "message": "hello, Otter" },
    { "index": 2, "message": "hello, Otter" },
    { "index": 3, "message": "hello, Otter" }
  ]
}
```

## YAML
```yaml
items:
  - index: 1
    message: hello, Otter
  - index: 2
    message: hello, Otter
  - index: 3
    message: hello, Otter
```

## TOML
```toml
[[items]]
index = 1
message = "hello, Otter"
[[items]]
index = 2
message = "hello, Otter"
[[items]]
index = 3
message = "hello, Otter"
```

## INI
```ini
[items]
first=hello, Otter
second=hello, Otter
third=hello, Otter
```

## CSS
```css
h1 { color: #2c7; font-family: system-ui; }
```

## SCSS
```scss
$brand: #2c7;
h1 { color: $brand; }
```

## Less
```less
@brand: #2c7;
h1 { color: @brand; }
```

## Markdown
```markdown
# Hello
This is `inline` and a list:
- one
- two
```

## Dockerfile
```dockerfile
FROM python:3.12-slim
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
```

## Makefile
```makefile
all:
	@echo "hello, Otter"
```

## CMake
```cmake
cmake_minimum_required(VERSION 3.20)
project(hello)
add_executable(hello main.c)
```

## NGINX
```nginx
server {
  listen 80;
  location / {
    return 200 "hello, Otter";
  }
}
```

## Apache Config
```apache
<VirtualHost *:80>
  DocumentRoot "/var/www/html"
</VirtualHost>
```

## Terraform (HCL)
```hcl
resource "null_resource" "hello" {
  triggers = { message = "hello, Otter" }
}
```

## ProtoBuf
```proto
syntax = "proto3";
message Greeting { int32 index = 1; string message = 2; }
```

## Diff
```diff
--- a/hello.txt
+++ b/hello.txt
@@
-Hello, World
+Hello, Otter
```

## Assembly (NASM)
```asm
section .text
global _start
_start:
  mov rax, 1 ; write
  mov rdi, 1 ; fd
  mov rsi, msg
  mov rdx, msgLen
  syscall
  mov rax, 60 ; exit
  xor rdi, rdi
  syscall
section .data
  msg db "hello, Otter", 10
  msgLen equ $-msg
```
