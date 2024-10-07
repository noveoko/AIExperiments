import re
from collections import defaultdict

class Person:
    def __init__(self, first_name, last_name, place, year_of_birth=None, year_of_death=None, children=None, spouse=None):
        self.first_name = first_name
        self.last_name = last_name
        self.place = place
        self.year_of_birth = year_of_birth
        self.year_of_death = year_of_death
        self.children = children or []
        self.spouse = spouse

    def __repr__(self):
        return (f"Person(first_name='{self.first_name}', last_name='{self.last_name}', "
                f"place='{self.place}', year_of_birth={self.year_of_birth}, "
                f"year_of_death={self.year_of_death}, children={self.children}, spouse={self.spouse})")

def parse_person_data(row):
    """Parse individual person data from a row."""
    match = re.match(r"^\s*(?P<first_name>\w+)\s+(?P<last_name>\w+)\s+(?P<place>\w+)\s+(?P<year_of_birth>\d{4})?", row)
    if match:
        return match.group('first_name'), match.group('last_name'), match.group('place'), match.group('year_of_birth')
    return None

def parse_death_data(row):
    """Parse death data including spouse and children information."""
    match = re.match(
        r"^\s*(?P<day>\d+)\s+(?P<month>\d+)\s+(?P<year_of_death>\d{4})\s+(?P<parish>\w+)\s+"
        r"(?P<first_name>\w+)\s+(?P<last_name>\w+)\s+(?P<age>\d+)\s+(?P<place>\w+)\s+(?P<info>.*)",
        row
    )
    if match:
        return match.groupdict()
    return None

def process_spouse_info(info, family_tree, last_name, first_name):
    """Process spouse information from the info string."""
    spouse_info = re.findall(r"żona ([\w\s]+)", info)
    if spouse_info:
        spouse_name = spouse_info[0].strip(",").strip().replace("z ", "")  # Clean up formatting
        spouse_parts = spouse_name.split()
        spouse_first_name, spouse_last_name = spouse_parts[0], spouse_parts[-1]

        if spouse_first_name in family_tree[spouse_last_name]:
            family_tree[last_name][first_name].spouse = family_tree[spouse_last_name][spouse_first_name]
            family_tree[spouse_last_name][spouse_first_name].spouse = family_tree[last_name][first_name]

def process_children_info(info, family_tree, last_name, first_name):
    """Process children information from the info string."""
    child_matches = re.findall(r"(synowie|córki): ([\w\s,]+)", info)
    for child_type, children_names in child_matches:
        children = [name.strip() for name in children_names.split(",")]
        for child_name in children:
            child_parts = child_name.split()
            if len(child_parts) >= 2:  # Ensure at least a first and last name
                child_first_name, child_last_name = child_parts[0], child_parts[-1]
                if child_first_name in family_tree[child_last_name]:
                    family_tree[child_last_name][child_first_name].place = family_tree[last_name][first_name].place
                    family_tree[last_name][first_name].children.append(family_tree[child_last_name][child_first_name])

def build_family_tree(data):
    family_tree = defaultdict(dict)

    for row in data:
        person_data = parse_person_data(row)
        if person_data:
            first_name, last_name, place, year_of_birth = person_data
            family_tree[last_name][first_name] = Person(first_name, last_name, place, year_of_birth=year_of_birth)
        else:
            death_data = parse_death_data(row)
            if death_data:
                first_name = death_data['first_name']
                last_name = death_data['last_name']
                year_of_death = int(death_data['year_of_death'])
                if first_name in family_tree[last_name]:
                    family_tree[last_name][first_name].year_of_death = year_of_death

                # Process spouse and children
                process_spouse_info(death_data['info'], family_tree, last_name, first_name)
                process_children_info(death_data['info'], family_tree, last_name, first_name)

    return family_tree

# Example usage:
with open("family_tree_data.txt", "r", encoding="utf-8") as file:
    data = file.readlines()

family_tree = build_family_tree(data)

# Print the family tree
for last_name, people in family_tree.items():
    print(f"Last name: {last_name}")
    for first_name, person in people.items():
        print(f"  {person}")
