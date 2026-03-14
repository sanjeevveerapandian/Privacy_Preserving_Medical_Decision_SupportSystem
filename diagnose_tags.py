import os
import re

def find_broken_tags(directory):
    patterns = [
        (re.compile(r'{{[[:space:]]*}}'), "Empty variable tag: {{}}"),
        (re.compile(r'{%[[:space:]]*%}'), "Empty block tag: {% %}"),
        (re.compile(r'{ {'), "Space in start variable tag: { {" ),
        (re.compile(r'} }'), "Space in end variable tag: } }" ),
        (re.compile(r'{ %'), "Space in start block tag: { %" ),
        (re.compile(r'% }'), "Space in end block tag: % }" ),
        (re.compile(r'{{[^{}]*$'), "Split variable tag (starts): {{"),
        (re.compile(r'^[^{}]*}}'), "Split variable tag (ends): }}"),
        (re.compile(r'{%[^{}%]*$'), "Split block tag (starts): {%"),
        (re.compile(r'^[^{}%]*%}'), "Split block tag (ends): %}"),
    ]
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.html'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r') as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines):
                            for pattern, desc in patterns:
                                if pattern.search(line):
                                    print(f"[{desc}] {path}:{i+1}")
                                    print(f"  Line: {line.strip()}")
                except Exception as e:
                    print(f"Error reading {path}: {e}")

if __name__ == "__main__":
    find_broken_tags('/Users/pyt/Downloads/1CP25-754 2/templates')
