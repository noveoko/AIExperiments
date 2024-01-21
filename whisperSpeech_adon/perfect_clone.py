# Do not forget to install all dependencies first:
!pip install -Uqq WhisperSpeech

def is_colab():
    try: import google.colab; return True
    except: return False

import torch
if not torch.cuda.is_available():
    if is_colab(): raise BaseException("Please change the runtime type to GPU. In the menu: Runtime -> Change runtime type (the free T4 instance is enough)")
    else:          raise BaseException("Currently the example notebook requires CUDA, make sure you are running this on a machine with a GPU.")

%load_ext autoreload
%autoreload 2

import torch
import torch.nn.functional as F

from IPython.display import Markdown, HTML

# check "7. Pipeline.ipynb"
from whisperspeech.pipeline import Pipeline

# let's start with the fast SD S2A model
pipe = Pipeline(s2a_ref='collabora/whisperspeech:s2a-q4-tiny-en+pl.model')


# CLONE any voice 1,2,3...

path_to_target_voice = '/content/grandma_voice_longer.mp3'

voice_embedding = pipe.extract_spk_emb(path_to_target_voice)

assert type(grandmas_voice_embedding) == torch.Tensor, f'Voice is not a torch.Tensor it is: type(grandmas_voice_embedding)'

generated_clones = []

for clone_id in range(10):
  clone = pipe.generate_to_file(f"clone_{clone_id}.mp3","Alesz to magia",grandmas_voice_embedding,lang="pl")
  generated_clones.append(clone)
  print(f'Created clone {clone_id}!')\

print('Now listen to each file and choose the best match!')

# Cell 1: Create an input box
my_favorite = input("Which voice sounds the best?: ")
assert int(my_favorite)


link_to_my_text = r'/content/three_roses.txt'

line_count = 0
with open(link_to_my_text, 'r') as f:
  for line in f.read().splitlines():
    if line.strip() != '':
      #create audio snippet
      line_count +=1
      line = line.strip()
      pipe.generate_to_file(text=line,fname=f"/content/clone_audio/clone_{line_count}.mp3", speaker=generated_clones[my_favorite], lang='pl', cps=15, step_callback=None)


import os
import glob
from pydub import AudioSegment

def concatenate_audio(directory_path, output_file):
    # Change to the specified directory
    os.chdir(directory_path)

    # Get a list of audio files in the directory
    audio_files = sorted(glob.glob("*.mp3"))

    # Concatenate audio files
    combined_audio = AudioSegment.silent()
    for audio_file in audio_files:
        audio_segment = AudioSegment.from_file(audio_file, format="mp3")
        combined_audio += audio_segment

    # Export the concatenated audio to a single MP3 file
    combined_audio.export(output_file, format="mp3")

# if __name__ == "__main__":
#     import argparse

#     # Create argument parser
#     parser = argparse.ArgumentParser(description="Concatenate audio files in a directory into a single MP3 file.")
#     parser.add_argument("directory", help="Path to the directory containing audio files.")
#     parser.add_argument("output_file", help="Path to the output MP3 file.")

#     # Parse arguments
#     args = parser.parse_args()

#     # Call the function with provided arguments
#     concatenate_audio(args.directory, args.output_file)

concatenate_audio(r"/content/clone_audio","Voice_clone_output.mp3")

# Viola! Enjoy your clone
