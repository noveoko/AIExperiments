I'll enhance the script with all these features. Here's the improved version:

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
from typing import List, Optional
import subprocess
import json

# Required libraries (install via pip)
try:
    from PIL import Image, ImageDraw, ImageFont
    from gtts import gTTS
    from moviepy.editor import (ImageClip, AudioFileClip, concatenate_videoclips,
                                CompositeVideoClip, VideoFileClip)
    from moviepy.video.fx.fadein import fadein
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.formatters import ImageFormatter
except ImportError as e:
    print(f"Missing required library: {e}")
    print("Install with: pip install Pillow gtts moviepy pygments")
    exit(1)


@dataclass
class Config:
    """Configuration for video generation"""
    width: int = 1920
    height: int = 1080
    bg_color: tuple = (0, 0, 0)
    text_color: tuple = (255, 255, 255)
    padding: int = 80
    transition_duration: float = 0.5
    enable_transitions: bool = True
    enable_counter: bool = True
    hyper_real_tts: bool = False
    
    @classmethod
    def from_file(cls, config_path: str):
        """Load config from JSON file"""
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                data = json.load(f)
                return cls(**data)
        return cls()
    
    def save(self, config_path: str):
        """Save config to JSON file"""
        with open(config_path, 'w') as f:
            json.dump(self.__dict__, f, indent=2)


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
    
    def __init__(self, config: Config):
        self.config = config
        self.width = config.width
        self.height = config.height
        self.bg_color = config.bg_color
        self.text_color = config.text_color
        self.padding = config.padding
        
        # Try to load a good monospace font
        self.font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/System/Library/Fonts/Monaco.ttf',
            '/System/Library/Fonts/Helvetica.ttc',
            'C:\\Windows\\Fonts\\consola.ttf',
            'C:\\Windows\\Fonts\\arial.ttf',
        ]
        
    def _get_font(self, size):
        """Load font with fallback"""
        for font_path in self.font_paths:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except Exception as e:
                    continue
        # Fallback to default
        return ImageFont.load_default()
    
    def _wrap_text(self, text: str, font: ImageFont, max_width: int) -> List[str]:
        """Wrap text to fit within max_width"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = font.getbbox(test_line)
            text_width = bbox[2] - bbox[0]
            
            if text_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    # Single word is too long, add it anyway
                    lines.append(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def _calculate_font_size(self, text: str, max_width: int, max_height: int, 
                            initial_size: int, min_size: int = 16) -> int:
        """Calculate optimal font size to fit text in bounds"""
        size = initial_size
        
        while size >= min_size:
            font = self._get_font(size)
            lines = self._wrap_text(text, font, max_width)
            
            # Estimate total height
            line_height = size + 10
            total_height = len(lines) * line_height
            
            if total_height <= max_height:
                return size
            
            size -= 2
        
        return min_size
    
    def _is_code_block(self, content: str) -> bool:
        """Detect if content is a code block"""
        return content.strip().startswith('```')
    
    def _add_slide_counter(self, img: Image.Image, slide_num: int, 
                          total_slides: int) -> Image.Image:
        """Add semi-transparent slide counter to bottom right"""
        if not self.config.enable_counter:
            return img
        
        draw = ImageDraw.Draw(img, 'RGBA')
        
        # Counter text
        counter_text = f"{slide_num}/{total_slides}"
        counter_font = self._get_font(36)
        
        # Get text size
        bbox = counter_font.getbbox(counter_text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Position in bottom right with padding
        x = self.width - text_width - 40
        y = self.height - text_height - 40
        
        # Draw semi-transparent background
        bg_padding = 15
        bg_rect = [
            x - bg_padding,
            y - bg_padding,
            x + text_width + bg_padding,
            y + text_height + bg_padding
        ]
        draw.rectangle(bg_rect, fill=(0, 0, 0, 128))
        
        # Draw text with 50% opacity
        text_color_alpha = self.text_color + (128,)
        draw.text((x, y), counter_text, fill=text_color_alpha, font=counter_font)
        
        return img
    
    def _render_code(self, code: str, slide_num: int = 1, 
                    total_slides: int = 1) -> Image.Image:
        """Render syntax-highlighted code with wrapping"""
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
        
        # Calculate available space
        max_width = self.width - (2 * self.padding)
        max_height = self.height - (2 * self.padding) - 100  # Reserve space for counter
        
        # Calculate optimal font size
        all_lines = code_content.split('\n')
        initial_font_size = 32
        font_size = self._calculate_font_size(
            '\n'.join(all_lines),
            max_width,
            max_height,
            initial_font_size,
            min_size=18
        )
        
        font = self._get_font(font_size)
        
        # Render each line with wrapping if needed
        y_offset = self.padding
        line_height = font_size + 8
        
        for line in all_lines:
            if not line.strip():
                y_offset += line_height
                continue
            
            # Wrap long lines
            wrapped_lines = self._wrap_text(line, font, max_width)
            
            for wrapped_line in wrapped_lines:
                if y_offset + line_height > self.height - self.padding - 100:
                    # Out of space
                    break
                
                # Simple syntax highlighting by color
                color = self.text_color
                if any(keyword in wrapped_line for keyword in ['def ', 'class ', 'import ', 'from ']):
                    color = (100, 200, 255)  # Blue for keywords
                elif wrapped_line.strip().startswith('#'):
                    color = (100, 200, 100)  # Green for comments
                elif any(char in wrapped_line for char in ['"', "'"]):
                    color = (255, 200, 100)  # Orange for strings
                
                draw.text((self.padding, y_offset), wrapped_line, 
                         fill=color, font=font)
                y_offset += line_height
        
        # Add slide counter
        img = self._add_slide_counter(img, slide_num, total_slides)
        
        return img
    
    def _render_text(self, title: str, content: str, slide_num: int = 1,
                    total_slides: int = 1) -> Image.Image:
        """Render text content with automatic wrapping and sizing"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        max_width = self.width - (2 * self.padding)
        
        # Title
        title_font_size = 60
        title_font = self._get_font(title_font_size)
        title_lines = self._wrap_text(title, title_font, max_width)
        
        y_offset = self.padding
        for line in title_lines:
            draw.text((self.padding, y_offset), line, 
                     fill=(100, 200, 255), font=title_font)
            y_offset += title_font_size + 15
        
        y_offset += 40  # Space after title
        
        # Content
        max_content_height = self.height - y_offset - self.padding - 100
        
        # Calculate optimal font size for content
        content_font_size = self._calculate_font_size(
            content,
            max_width,
            max_content_height,
            initial_size=40,
            min_size=24
        )
        
        content_font = self._get_font(content_font_size)
        line_height = content_font_size + 20
        
        for line in content.split('\n'):
            if not line.strip():
                y_offset += line_height // 2
                continue
            
            # Handle bullet points
            if line.strip().startswith('- '):
                line = '  • ' + line.strip()[2:]
            elif line.strip().startswith('* '):
                line = '  • ' + line.strip()[2:]
            
            # Wrap long lines
            wrapped_lines = self._wrap_text(line, content_font, max_width - 40)
            
            for wrapped_line in wrapped_lines:
                if y_offset + line_height > self.height - self.padding - 100:
                    break
                
                draw.text((self.padding, y_offset), wrapped_line, 
                         fill=self.text_color, font=content_font)
                y_offset += line_height
        
        # Add slide counter
        img = self._add_slide_counter(img, slide_num, total_slides)
        
        return img
    
    def render_slide(self, slide: Slide, output_path: str, slide_num: int = 1,
                    total_slides: int = 1):
        """Render a single slide to an image file"""
        if self._is_code_block(slide.visual_content):
            img = self._render_code(slide.visual_content, slide_num, total_slides)
        else:
            img = self._render_text(slide.title, slide.visual_content, 
                                   slide_num, total_slides)
        
        img.save(output_path)
        print(f"Rendered slide {slide_num}/{total_slides}: {output_path}")


class AudioGenerator:
    """Generates narration audio from text"""
    
    def __init__(self, config: Config, language='en', slow=False):
        self.config = config
        self.language = language
        self.slow = slow
        self.hyper_real = config.hyper_real_tts
        
        if self.hyper_real:
            self._check_coqui_installation()
    
    def _check_coqui_installation(self):
        """Check if Coqui TTS is installed for hyper-real mode"""
        try:
            import TTS
            print("✓ Coqui TTS detected for hyper-real voice generation")
        except ImportError:
            print("⚠ Hyper-real mode requires Coqui TTS")
            print("Install with: pip install TTS")
            print("Falling back to gTTS...")
            self.hyper_real = False
    
    def _generate_hyper_real_audio(self, text: str, output_path: str) -> float:
        """Generate high-quality audio using Coqui TTS"""
        from TTS.api import TTS
        
        # Initialize TTS with a high-quality model
        # Using XTTS-v2 for natural, human-like speech
        try:
            print("  Loading neural TTS model (first time may take a while)...")
            tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
            
            # Generate audio
            tts.tts_to_file(text=text, file_path=output_path)
            
            # Get duration
            audio = AudioFileClip(output_path)
            duration = audio.duration
            audio.close()
            
            print(f"  Generated hyper-real audio: {output_path} ({duration:.1f}s)")
            return duration
            
        except Exception as e:
            print(f"  ⚠ Hyper-real TTS failed: {e}")
            print("  Falling back to gTTS...")
            return self._generate_standard_audio(text, output_path)
    
    def _generate_standard_audio(self, text: str, output_path: str) -> float:
        """Generate audio using standard gTTS"""
        tts = gTTS(text=text, lang=self.language, slow=self.slow)
        tts.save(output_path)
        
        # Get duration
        audio = AudioFileClip(output_path)
        duration = audio.duration
        audio.close()
        
        return duration
    
    def generate_audio(self, text: str, output_path: str) -> float:
        """Generate audio file and return duration in seconds"""
        if self.hyper_real:
            duration = self._generate_hyper_real_audio(text, output_path)
        else:
            duration = self._generate_standard_audio(text, output_path)
        
        print(f"Generated audio: {output_path} ({duration:.1f}s)")
        return duration


class VideoBuilder:
    """Combines images and audio into video segments"""
    
    def __init__(self, config: Config):
        self.config = config
    
    def create_video_segment(self, image_path: str, audio_path: str, 
                            output_path: str):
        """Create a video segment from image and audio with fade-in transition"""
        # Load audio to get duration
        audio = AudioFileClip(audio_path)
        
        # Create video clip from image with audio duration
        video = ImageClip(image_path, duration=audio.duration)
        
        # Apply fade-in transition if enabled
        if self.config.enable_transitions:
            video = fadein(video, self.config.transition_duration)
        
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
        final = concatenate_videoclips(clips, method="compose")
        
        final.write_videofile(output_path, fps=24, codec='libx264',
                            audio_codec='aac')
        
        for clip in clips:
            clip.close()
        final.close()
        
        print(f"Final video created: {output_path}")


def generate_learning_module(markdown_path: str, output_dir: str = "output",
                            config: Optional[Config] = None):
    """
    Main function to generate complete learning module
    
    Steps:
    1. Parse markdown into slides
    2. Render each slide as an image
    3. Generate narration audio for each slide
    4. Combine image + audio into video segments
    5. Concatenate all segments into final video
    """
    
    # Use provided config or create default
    if config is None:
        config = Config()
    
    # Setup
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    temp_dir = output_path / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    # Step 1: Parse markdown
    print("Step 1: Parsing markdown...")
    parser = MarkdownParser(markdown_path)
    slides = parser.parse()
    total_slides = len(slides)
    print(f"Found {total_slides} slides")
    
    # Step 2-4: Process each slide
    renderer = SlideRenderer(config)
    audio_gen = AudioGenerator(config)
    video_builder = VideoBuilder(config)
    
    segment_paths = []
    
    for i, slide in enumerate(slides, 1):
        print(f"\nProcessing slide {i}/{total_slides}: {slide.title}")
        
        # Render image with counter
        image_path = temp_dir / f"slide_{i:03d}.png"
        renderer.render_slide(slide, str(image_path), i, total_slides)
        
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
    print(f"  Total slides: {total_slides}")
    total_duration = sum(
        AudioFileClip(str(temp_dir / f'slide_{i:03d}.mp3')).duration 
        for i in range(1, total_slides + 1)
    )
    print(f"  Total duration: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
    
    # Save config
    config.save(str(output_path / "config.json"))


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate learning module videos from markdown'
    )
    parser.add_argument('markdown_file', help='Path to markdown file')
    parser.add_argument('output_dir', nargs='?', default='output',
                       help='Output directory (default: output)')
    parser.add_argument('--hyper-real', action='store_true',
                       help='Enable state-of-the-art neural TTS (requires Coqui TTS)')