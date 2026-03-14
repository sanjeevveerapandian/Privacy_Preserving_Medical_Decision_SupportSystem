import os
import re

def fix_split_tags(directory):
    # Regex to find split variable tags: {{ ... \n ... }}
    var_split_pattern = re.compile(r'{{([^{}]*)\n\s*([^{}]*)}}')
    block_split_pattern = re.compile(r'{%([^{}%]*)\n\s*([^{}%]*)%}')
    
    # Regex for space issues
    space_var_start = re.compile(r'{\s{')
    space_var_end = re.compile(r'}\s}')
    space_block_start = re.compile(r'{\s%')
    space_block_end = re.compile(r'%\s}')

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.html'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r') as f:
                        content = f.read()
                    
                    original_content = content
                    
                    # Fix space issues first
                    content = space_var_start.sub('{{', content)
                    content = space_var_end.sub('}}', content)
                    content = space_block_start.sub('{%', content)
                    content = space_block_end.sub('%}', content)
                    
                    # Fix split tags (multiple passes for complex ones)
                    for _ in range(3):
                        content = var_split_pattern.sub(r'{{\1 \2}}', content)
                        content = block_split_pattern.sub(r'{%\1 \2%}', content)
                    
                    if content != original_content:
                        with open(path, 'w') as f:
                            f.write(content)
                        print(f"Fixed tags in {path}")
                        
                except Exception as e:
                    print(f"Error processing {path}: {e}")

if __name__ == "__main__":
    fix_split_tags('/Users/pyt/Downloads/1CP25-754 2/templates')
