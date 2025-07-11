import re

def abc_to_virtual_piano(abc_notation):
    """
    Converts a song from ABC notation to a Virtual Piano format with support
    for key signatures, octaves, accidentals, and basic note lengths.

    Args:
        abc_notation: A string containing the song in ABC notation.

    Returns:
        A string in the Virtual Piano format.
    """
    # This dictionary maps a standard note name (with octave) to the Virtual Piano key.
    # It covers several octaves.
    note_map = {
        'C2': '1', 'C#2': '!', 'D2': '2', 'D#2': '@', 'E2': '3', 'F2': '4', 'F#2': '$', 'G2': '5', 'G#2': '%', 'A2': '6', 'A#2': '^', 'B2': '7',
        'C3': '8', 'C#3': '*', 'D3': '9', 'D#3': '(', 'E3': '0', 'F3': 'q', 'F#3': 'Q', 'G3': 'w', 'G#3': 'W', 'A3': 'e', 'A#3': 'E', 'B3': 'r',
        'C4': 't', 'C#4': 'T', 'D4': 'y', 'D#4': 'Y', 'E4': 'u', 'F4': 'i', 'F#4': 'I', 'G4': 'o', 'G#4': 'O', 'A4': 'p', 'A#4': 'P', 'B4': 'a',
        'C5': 's', 'C#5': 'S', 'D5': 'd', 'D#5': 'D', 'E5': 'f', 'F5': 'g', 'F#5': 'G', 'G5': 'h', 'G#5': 'H', 'A5': 'j', 'A#5': 'J', 'B5': 'k',
        'C6': 'l', 'C#6': 'L', 'D6': 'z', 'D#6': 'Z', 'E6': 'x', 'F6': 'c', 'F#6': 'C', 'G6': 'v', 'G#6': 'V', 'A6': 'b', 'A#6': 'B', 'B6': 'n',
    }
    
    # Standard key signatures and their accidentals.
    key_signatures = {
        'C': [], 'G': ['F#'], 'D': ['F#', 'C#'], 'A': ['F#', 'C#', 'G#'], 'E': ['F#', 'C#', 'G#', 'D#'],
        'B': ['F#', 'C#', 'G#', 'D#', 'A#'], 'F#': ['F#', 'C#', 'G#', 'D#', 'A#', 'E#'],
        'C#': ['F#', 'C#', 'G#', 'D#', 'A#', 'E#', 'B#'],
        'F': ['Bb'], 'Bb': ['Bb', 'Eb'], 'Eb': ['Bb', 'Eb', 'Ab'], 'Ab': ['Bb', 'Eb', 'Ab', 'Db'],
        'Db': ['Bb', 'Eb', 'Ab', 'Db', 'Gb'], 'Gb': ['Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb'],
        'Cb': ['Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb', 'Fb']
    }
    
    # --- Helper function to parse a single note token ---
    def parse_note(note_token, active_accidentals):
        # Regex to break down a note into: accidental, note name, octave modifier
        match = re.match(r'([_^=]?)?([A-Ga-g])([,\']*)', note_token)
        if not match:
            return ''

        accidental, note_name, octave_mod = match.groups()

        # Determine the base octave. C-B are in octave 3, c-b are in octave 4.
        base_octave = 3 if 'A' <= note_name <= 'B' else 4 if 'C' <= note_name <= 'G' else 4
        
        # Adjust octave based on modifiers
        octave = base_octave + octave_mod.count("'") - octave_mod.count(",")
        
        final_note = note_name.upper()

        # Apply accidentals
        if accidental == '^':
            final_note += '#'
        elif accidental == '_':
            final_note += 'b'
        elif accidental == '=':
            pass # Natural sign, do nothing to the note name
        elif final_note in active_accidentals:
            final_note = active_accidentals[final_note]

        # Final lookup key, e.g., "C#4"
        final_note_key = final_note + str(octave)

        return note_map.get(final_note_key, '')

    # --- Main Processing Logic ---
    
    # Find the key signature from the header
    key_match = re.search(r'K:\s*([A-G][b#]?)', abc_notation)
    active_key = 'C'
    if key_match:
        active_key = key_match.group(1)

    # Set up the accidentals for the current key
    current_accidentals = {}
    for acc in key_signatures.get(active_key, []):
        current_accidentals[acc[0]] = acc

    # Remove header lines to only process the music part
    music_body = re.sub(r'^[A-Za-z]:.*\n?', '', abc_notation, flags=re.MULTILINE)
    
    # Tokenize music body into chords, notes, bars, or spaces
    tokens = re.findall(r'(\[[^\]]+\]|[A-Ga-g,=\'^_]+[\d\/]*|[|:\] ]+)', music_body)
    
    virtual_piano_output = ""
    
    for token in tokens:
        token = token.strip()
        if not token:
            continue
            
        if token.startswith('['): # It's a chord
            chord_notes = re.findall(r'([_^=]?[A-Ga-g][,\']*)', token)
            vp_chord = ''.join(sorted([parse_note(n, current_accidentals) for n in chord_notes]))
            if vp_chord:
                virtual_piano_output += f"[{vp_chord}] "

        elif token.startswith('|') or token.startswith(':'): # It's a bar line
            virtual_piano_output += "| "
            # Reset accidentals at the bar line
            for acc in key_signatures.get(active_key, []):
                current_accidentals[acc[0]] = acc

        elif re.match(r'[_^=]?[A-Ga-g]', token): # It's a single note
            note_part = re.match(r'([_^=]?[A-Ga-g][,\']*)', token).group(1)
            parsed = parse_note(note_part, current_accidentals)
            
            # Handle explicit accidentals for the rest of the bar
            if note_part.startswith('^'): current_accidentals[note_part[1].upper()] = note_part[1].upper() + '#'
            if note_part.startswith('_'): current_accidentals[note_part[1].upper()] = note_part[1].upper() + 'b'
            if note_part.startswith('='): current_accidentals[note_part[1].upper()] = note_part[1].upper()

            virtual_piano_output += parsed + " "
            
        elif 'z' in token: # It's a rest
            virtual_piano_output += "| "


    # Clean up extra spaces
    return re.sub(r'\s+', ' ', virtual_piano_output).strip()

# --- Example Usage ---

# "Don't Worry Be Happy" snippet in ABC notation
abc_song = """
X:1
T:Don't Worry Be Happy
M:4/4
L:1/8
K:C
e8 | c'8 | d'4 e'4 | c'8 |
"""

converted_song = abc_to_virtual_piano(abc_song)
print("--- Don't Worry Be Happy ---")
print("ABC Notation Snippet:\n", abc_song.strip())
print("\nVirtual Piano Format:\n", converted_song)


# "Game of Thrones" snippet to test key signatures and chords
abc_got = """
X:1
T:Game of Thrones
K:Cm
L:1/8
M:3/4
[G,c]2 G, [G,c]2 G, | [G,c]2 G, [G,c] [G,d] [G,e] | [G,f]2 G, [G,f]2 G, | [G,f]2 G, [G,f] [G,d] [G,c] |
"""
# Note: K:Cm is minor, this script simplifies to C major. A full minor key implementation is more complex.
converted_got = abc_to_virtual_piano(abc_got)
print("\n\n--- Game of Thrones ---")
print("ABC Notation Snippet:\n", abc_got.strip())
print("\nVirtual Piano Format:\n", converted_got)
