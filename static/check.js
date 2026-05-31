const fs = require("fs");
const js = fs.readFileSync("static/app.js", "utf8");

// Check for unclosed template literals
const lines = js.split("\n");
let inTemplate = false;
let templateStart = 0;

for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  for (let j = 0; j < line.length; j++) {
    if (line[j] === "`") {
      if (j === 0 || line[j-1] !== "\\") {
        inTemplate = !inTemplate;
        if (inTemplate) templateStart = i + 1;
      }
    }
  }
}
if (inTemplate) {
  console.log("UNCLOSED template string starting at line:", templateStart);
} else {
  console.log("OK: All template literals closed");
}

// Check for unclosed brackets (rough check, skip strings)
let parens = 0, braces = 0, brackets = 0;
let inStr = null;
for (let i = 0; i < js.length; i++) {
  const c = js[i];
  if (inStr) {
    if (c === "\\") { i++; }
    else if (c === inStr) { inStr = null; }
    continue;
  }
  if (c === '"' || c === "'" || c === "`") { inStr = c; continue; }
  if (c === "(") parens++;
  if (c === ")") parens--;
  if (c === "{") braces++;
  if (c === "}") braces--;
  if (c === "[") brackets++;
  if (c === "]") brackets--;
}
console.log("Braces balance: ()=" + parens + " {}=" + braces + " []=" + brackets);
if (parens !== 0 || braces !== 0 || brackets !== 0) {
  console.log("UNBALANCED braces!");
} else {
  console.log("OK: All braces balanced");
}

// Try to compile
try {
  new Function(js);
  console.log("OK: JS compiles successfully");
} catch(e) {
  console.log("COMPILE ERROR:", e.message);
}