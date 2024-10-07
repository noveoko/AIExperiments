# Family Tree Builder

This project builds a fully connected family tree from textual data, mapping out relationships between individuals, including parents, children, and spouses. It processes raw data from text files and constructs a tree structure that allows tracing of bi-directional relationships between family members.

## Features

- **Bi-Directional Relationships:** Links parents to children and spouses in both directions.
- **Handles Missing Data:** Creates placeholders for individuals when incomplete information is available (e.g., a child or spouse without full details).
- **Flexible Data Parsing:** Parses family data from text files and dynamically grows the family tree based on available information.
- **Person Representation:** Each person object stores their first name, last name, place, birth year, death year, children, parents, and spouse.

## How It Works

1. **Input Format:** The input file should contain rows representing people, with a variety of family-related information, such as:
   - Basic details: First name, last name, place, birth year.
   - Death records: Date of death, age, spouse, children.
   
2. **Family Tree Construction:** The script reads data from the input file, extracts person information, and builds a complete family tree. Relationships between people (spouses, children, parents) are dynamically added and updated.

3. **Bi-Directional Relationships:** When a person is referenced as a spouse or child, the corresponding relationships are established in both directions, so the tree reflects the full family network.

## Data Format

The input text file should be formatted like this:

- **Basic Person Information:**
  ```
  FirstName LastName Place YearOfBirth
  ```
  Example:
  ```
  John Smith London 1920
  ```

- **Death Records:**
  ```
  Day Month YearOfDeath Parish FirstName LastName Age Place AdditionalInfo
  ```
  Example:
  ```
  15 04 1985 StMary John Smith 65 London żona Mary Smith synowie: Paul Smith, córki: Sarah Smith
  ```

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/family-tree-builder.git
   ```
   
2. Navigate to the project directory:
   ```bash
   cd family-tree-builder
   ```

3. Install the necessary dependencies (Python 3.x required). This project uses the Python standard library, so no additional dependencies are required.

## Usage

1. **Prepare the Input File:**
   Place your family tree data in a text file, e.g., `family_tree_data.txt`, following the format described above.

2. **Run the Script:**
   ```bash
   python family_tree_builder.py
   ```

3. **Output:**
   The script will print out the constructed family tree, showing each person and their relationships (children, spouse, parents).

Example output:
```
Last name: Smith
  Person(first_name='John', last_name='Smith', place='London', year_of_birth=1920, year_of_death=1985, children=2, spouse=Mary, parents=[])
  Person(first_name='Paul', last_name='Smith', place='London', year_of_birth=None, year_of_death=None, children=0, spouse=None, parents=['John'])
  Person(first_name='Sarah', last_name='Smith', place='London', year_of_birth=None, year_of_death=None, children=0, spouse=None, parents=['John'])
```

## Customization

- **Parsing Logic:** You can extend the regular expressions used for parsing to support more complex family structures or data formats.
- **Visualization:** Consider exporting the tree into formats such as `.json` or `.dot` to visualize the relationships using external tools.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue to improve the project.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
```

### Key Sections:
- **Features:** Highlights the core functionalities of the project.
- **Data Format:** Provides an example of the expected input format.
- **Installation & Usage:** Guides the user through setting up and running the program.
- **Customization:** Suggests ways to expand or modify the project.
  
Feel free to adjust the repository name, license, and any other details specific to your project!
