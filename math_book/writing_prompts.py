import re

# Open the input file
with open("input.txt", "r") as file:
    # Read the contents of the file
    contents = file.read()
    
    # Split the contents into lines
    lines = contents.splitlines()
    
    for line in lines:
        if x_match := re.search(r"^([\d.]+) (.*)$", line):
            # Print section heading
            print(f"## {x_match.group(2)}\n")
        elif a_match := re.search(r"^\s*([a-z]\.)\s+(.*)$", line):
            # Print subsection heading
            print(f"### {a_match.group(2)}\n")
import re

# Open the input file
with open("input.txt", "r") as file:
    # Read the contents of the file
    contents = file.read()
    
    # Split the contents into lines
    lines = contents.splitlines()
    
    sections = []
    chunks = []
    for line in lines:
        if x_match := re.search(r"^([\d.]+) (.*)$", line):
            section = x_match.group(2)
            sections.append(section)
            chunks.append([])
        elif a_match := re.search(r"^\s*([a-z]\.)\s+(.*)$", line):
            chunks[-1].append(a_match.group(2))

prompts = '''Book: "Pre-Algebra for Adults that Suck at Math but really want to learn it"
Section:{section}
Subsection:{sub_section}

Write {sub_section}\n\n
'''

blob = ''

for count, section in enumerate(sections):
    subsections = chunks[count]
    for sub in subsections:
      blob += prompts.format(section=section, sub_section=sub)

with open('writing_prompts.txt', 'w') as f:
  f.write(blob)
