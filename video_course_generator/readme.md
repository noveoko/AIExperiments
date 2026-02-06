I'll help you create a system that transforms technical documentation into engaging video learning modules. Let me break this down into two main components:

## Component 1: LLM Prompt for Markdown Generation

First, here's a prompt you can use with an LLM to generate the structured markdown:

```markdown
You are creating an engaging video learning module from technical documentation. Generate a markdown file with the following structure:

# [Module Title]

## Slide 1: [Topic]
### Visual
[What appears on screen - text, code, diagrams]

### Narration
[What the voice says - should complement, not repeat the visual content]

### Duration
[Estimated seconds based on narration length]

---

Continue this pattern for each concept in the documentation.

**Guidelines:**
- Break complex topics into digestible slides (30-90 seconds each)
- Visuals: Use concise bullet points, code snippets, or key terms
- Narration: Explain WHY and HOW, provide context, tell a story
- Code: Syntax-highlighted, well-commented
- Use analogies and real-world examples in narration
- Each slide should have ONE clear learning objective
- Progressive disclosure: build concepts incrementally
```

## Component 2: Python Video Generator

Here's a complete Python script that converts the markdown into videos:

```python
#!/usr/bin/env python3
"""
Video Learning Module Generator
Converts structured markdown into narrated video segments
"""

import re
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List
import subprocess

# Required libraries (install via pip)
try:
    from PIL import Image, ImageDraw, ImageFont
    from gtts import gTTS
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.formatters import ImageFormatter
except ImportError as e:
    print(f"Missing required library: {e}")
    print("Install with: pip install Pillow gtts moviepy pygments")
    exit(1)


@dataclass
class Slide:
    """Represents a single slide in the learning module"""
    title: str
    visual_content: str
    narration: str
    duration: int = None  # Auto-calculated from narration if not provided


class MarkdownParser:
    """Parses the structured markdown into Slide objects"""
    
    def __init__(self, markdown_path: str):
        self.markdown_path = markdown_path
        with open(markdown_path, 'r', encoding='utf-8') as f:
            self.content = f.read()
    
    def parse(self) -> List[Slide]:
        """Extract slides from markdown"""
        slides = []
        
        # Split by slide separators (---) or ## headers
        slide_pattern = r'## Slide \d+: (.+?)\n### Visual\n(.+?)\n### Narration\n(.+?)(?:\n### Duration\n(\d+))?(?=\n##|\n---|\Z)'
        
        matches = re.finditer(slide_pattern, self.content, re.DOTALL)
        
        for match in matches:
            title = match.group(1).strip()
            visual = match.group(2).strip()
            narration = match.group(3).strip()
            duration = int(match.group(4)) if match.group(4) else None
            
            slides.append(Slide(
                title=title,
                visual_content=visual,
                narration=narration,
                duration=duration
            ))
        
        return slides


class SlideRenderer:
    """Renders slides as images with syntax highlighting"""
    
    def __init__(self, width=1920, height=1080):
        self.width = width
        self.height = height
        self.bg_color = (0, 0, 0)  # Black background
        self.text_color = (255, 255, 255)  # White text
        self.padding = 80
        
        # Try to load a good monospace font
        self.font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
            '/System/Library/Fonts/Monaco.ttf',
            'C:\\Windows\\Fonts\\consola.ttf',
        ]
        
    def _get_font(self, size):
        """Load font with fallback"""
        for font_path in self.font_paths:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except:
                    continue
        # Fallback to default
        return ImageFont.load_default()
    
    def _is_code_block(self, content: str) -> bool:
        """Detect if content is a code block"""
        return content.strip().startswith('```')
    
    def _render_code(self, code: str) -> Image.Image:
        """Render syntax-highlighted code"""
        # Extract language and code
        lines = code.strip().split('\n')
        language = 'python'  # default
        
        if lines[0].startswith('```'):
            language = lines[0][3:].strip() or 'python'
            code_content = '\n'.join(lines[1:-1])
        else:
            code_content = code
        
        # Create image with black background
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Use Pygments for syntax highlighting (simplified approach)
        font = self._get_font(32)
        
        # Split code into lines and render
        y_offset = self.padding
        for line in code_content.split('\n'):
            draw.text((self.padding, y_offset), line, 
                     fill=self.text_color, font=font)
            y_offset += 45
        
        return img
    
    def _render_text(self, title: str, content: str) -> Image.Image:
        """Render text content"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Title
        title_font = self._get_font(60)
        draw.text((self.padding, self.padding), title, 
                 fill=(100, 200, 255), font=title_font)
        
        # Content
        content_font = self._get_font(40)
        y_offset = self.padding + 120
        
        # Wrap text manually (simple approach)
        max_width = self.width - (2 * self.padding)
        
        for line in content.split('\n'):
            # Simple bullet point handling
            if line.strip().startswith('- '):
                line = '  • ' + line.strip()[2:]
            
            draw.text((self.padding, y_offset), line, 
                     fill=self.text_color, font=content_font)
            y_offset += 60
        
        return img
    
    def render_slide(self, slide: Slide, output_path: str):
        """Render a single slide to an image file"""
        if self._is_code_block(slide.visual_content):
            img = self._render_code(slide.visual_content)
        else:
            img = self._render_text(slide.title, slide.visual_content)
        
        img.save(output_path)
        print(f"Rendered slide: {output_path}")


class AudioGenerator:
    """Generates narration audio from text"""
    
    def __init__(self, language='en', slow=False):
        self.language = language
        self.slow = slow
    
    def generate_audio(self, text: str, output_path: str) -> float:
        """Generate audio file and return duration in seconds"""
        tts = gTTS(text=text, lang=self.language, slow=self.slow)
        tts.save(output_path)
        
        # Get duration using AudioFileClip
        audio = AudioFileClip(output_path)
        duration = audio.duration
        audio.close()
        
        print(f"Generated audio: {output_path} ({duration:.1f}s)")
        return duration


class VideoBuilder:
    """Combines images and audio into video segments"""
    
    def create_video_segment(self, image_path: str, audio_path: str, 
                            output_path: str):
        """Create a video segment from image and audio"""
        # Load audio to get duration
        audio = AudioFileClip(audio_path)
        
        # Create video clip from image with audio duration
        video = ImageClip(image_path, duration=audio.duration)
        video = video.set_audio(audio)
        
        # Write video file
        video.write_videofile(output_path, fps=1, codec='libx264',
                            audio_codec='aac', verbose=False, logger=None)
        
        video.close()
        audio.close()
        
        print(f"Created video segment: {output_path}")
    
    def concatenate_videos(self, video_paths: List[str], output_path: str):
        """Combine multiple video segments into final module"""
        clips = [VideoFileClip(path) for path in video_paths]
        final = concatenate_videoclips(clips)
        
        final.write_videofile(output_path, fps=24, codec='libx264',
                            audio_codec='aac')
        
        for clip in clips:
            clip.close()
        final.close()
        
        print(f"Final video created: {output_path}")


def generate_learning_module(markdown_path: str, output_dir: str = "output"):
    """
    Main function to generate complete learning module
    
    Steps:
    1. Parse markdown into slides
    2. Render each slide as an image
    3. Generate narration audio for each slide
    4. Combine image + audio into video segments
    5. Concatenate all segments into final video
    """
    
    # Setup
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    temp_dir = output_path / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    # Step 1: Parse markdown
    print("Step 1: Parsing markdown...")
    parser = MarkdownParser(markdown_path)
    slides = parser.parse()
    print(f"Found {len(slides)} slides")
    
    # Step 2-4: Process each slide
    renderer = SlideRenderer()
    audio_gen = AudioGenerator()
    video_builder = VideoBuilder()
    
    segment_paths = []
    
    for i, slide in enumerate(slides, 1):
        print(f"\nProcessing slide {i}/{len(slides)}: {slide.title}")
        
        # Render image
        image_path = temp_dir / f"slide_{i:03d}.png"
        renderer.render_slide(slide, str(image_path))
        
        # Generate audio
        audio_path = temp_dir / f"slide_{i:03d}.mp3"
        duration = audio_gen.generate_audio(slide.narration, str(audio_path))
        
        # Create video segment
        segment_path = temp_dir / f"segment_{i:03d}.mp4"
        video_builder.create_video_segment(
            str(image_path), str(audio_path), str(segment_path)
        )
        
        segment_paths.append(str(segment_path))
    
    # Step 5: Concatenate segments
    print("\nStep 5: Creating final video...")
    final_path = output_path / "learning_module.mp4"
    video_builder.concatenate_videos(segment_paths, str(final_path))
    
    print(f"\n✓ Complete! Final video: {final_path}")
    print(f"  Total slides: {len(slides)}")
    print(f"  Total duration: {sum(AudioFileClip(temp_dir / f'slide_{i:03d}.mp3').duration for i in range(1, len(slides)+1)):.1f}s")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python video_generator.py <markdown_file> [output_dir]")
        sys.exit(1)
    
    markdown_file = sys.argv[1]
    output_directory = sys.argv[2] if len(sys.argv) > 2 else "output"
    
    generate_learning_module(markdown_file, output_directory)
```

## Step-by-Step Usage Instructions

### Step 1: Install Dependencies

```bash
# Install required Python packages
pip install Pillow gtts moviepy pygments

# MoviePy also requires ffmpeg - install based on your OS:
# Ubuntu/Debian:
sudo apt-get install ffmpeg

# macOS:
brew install ffmpeg

# Windows: Download from https://ffmpeg.org/download.html
```

### Step 2: Create Your Markdown Content

Either manually or use an LLM with the prompt above. Example structure:

```markdown
# Introduction to Python Functions

## Slide 1: What is a Function?
### Visual
- Reusable block of code
- Takes inputs (parameters)
- Returns outputs
- Defined using `def` keyword

### Narration
Think of a function like a recipe. Just as a recipe takes ingredients and produces a dish, a function takes inputs and produces an output. This lets us write code once and use it many times, making our programs cleaner and more efficient.

### Duration
15

## Slide 2: Basic Function Syntax
### Visual
```python
def greet(name):
    return f"Hello, {name}!"

result = greet("Alice")
print(result)  # Output: Hello, Alice!
```

### Narration
Here's the basic anatomy. We use the def keyword, followed by the function name and parentheses. Inside the parentheses, we define parameters. The code block is indented, and we use return to send back a value. Simple, but powerful.
```

### Step 3: Run the Generator

```bash
python video_generator.py your_module.md output_folder
```

### Step 4: Review and Iterate

The script will:
1. Parse your markdown into slide objects
2. Render each slide as a 1920x1080 image (black background, white/colored text)
3. Generate MP3 narration using Google Text-to-Speech
4. Combine each image+audio into a video segment
5. Concatenate all segments into the final learning module

## Customization Options

**Change voice settings** (in `AudioGenerator.__init__`):
```python
# Slower speech for complex topics
AudioGenerator(language='en', slow=True)

# Different language
AudioGenerator(language='es')  # Spanish
```

**Adjust visual style** (in `SlideRenderer.__init__`):
```python
self.bg_color = (20, 20, 30)  # Dark blue background
self.text_color = (200, 255, 200)  # Light green text
```

**Resolution** (in `SlideRenderer.__init__`):
```python
SlideRenderer(width=1280, height=720)  # 720p instead of 1080p
```

This system gives you a complete pipeline from documentation to engaging video content. The key is crafting good markdown with complementary visual/narration content!