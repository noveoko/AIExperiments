# zForm - Depth Map to 3D Mesh Converter
## Blender Addon Documentation

zForm is a powerful Blender addon that transforms depth maps and images into detailed 3D meshes with just a few clicks. This tool streamlines the process of converting 2D content into 3D, making it perfect for creating relief sculptures, terrain, architectural details, and more.

## Table of Contents
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Detailed Usage Guide](#detailed-usage-guide)
- [Tips and Best Practices](#tips-and-best-practices)
- [Troubleshooting](#troubleshooting)
- [Technical Requirements](#technical-requirements)

## Installation

1. Download the `zform.py` file
2. Open Blender and go to Edit > Preferences
3. Select the "Add-ons" tab
4. Click "Install..." and navigate to the downloaded `zform.py` file
5. Enable the addon by checking the box next to "3D View: zForm - Depth Map to 3D Mesh"

## Quick Start

1. Switch to the 3D View
2. Open the sidebar (press N if not visible)
3. Find the "zForm" tab
4. Click the folder icon to select your base image
5. Click the second folder icon to select your depth map
6. Adjust settings as needed
7. Click "Create 3D Mesh"

## Detailed Usage Guide

### Preparing Your Images

#### Base Image Requirements:
- Formats: PNG, JPG, JPEG
- Recommended resolution: 2048x2048 or higher
- Keep file size reasonable (under 4096x4096 for best performance)

#### Depth Map Requirements:
- Grayscale image
- White represents highest points
- Black represents lowest points
- Same resolution as base image
- Format: PNG recommended for best precision

### Settings Explained

#### Mesh Settings:

**Subdivision Level** (1-256)
- Controls mesh detail
- Higher values create more geometry
- Recommended starting point: 32
- Increase for more detail, decrease for better performance

**Depth Strength** (0-10)
- Controls how pronounced the depth effect is
- Higher values create more dramatic height differences
- Recommended starting point: 1.0
- Adjust based on your depth map's contrast

**Smoothing Factor** (0-1)
- Controls edge smoothing
- 0 = Sharp edges
- 1 = Maximum smoothing
- Recommended starting point: 0.5

#### Material Settings:

**Metallic** (0-1)
- Controls metallic appearance
- 0 = Non-metallic
- 1 = Fully metallic
- Recommended: 0 for most cases

**Roughness** (0-1)
- Controls surface roughness
- 0 = Mirror finish
- 1 = Completely matte
- Recommended: 0.5 for a semi-glossy finish

**IOR** (1.0-3.0)
- Index of Refraction
- Affects reflection intensity
- Common values:
  - 1.45 = Glass
  - 1.33 = Water
  - 1.52 = Plastic

### Step-by-Step Tutorial

1. **Prepare Your Workspace**
   - Create a new Blender file
   - Switch to the 3D View
   - Delete the default cube (optional)
   - Open the zForm panel

2. **Load Your Images**
   - Click the folder icon next to "Image"
   - Navigate to and select your base image
   - Click the folder icon next to "Depth Map"
   - Navigate to and select your depth map
   - Both images should now appear in the file paths

3. **Adjust Basic Settings**
   - Start with default settings
   - Set Subdivision Level to 32
   - Set Depth Strength to 1.0
   - Set Smoothing Factor to 0.5

4. **Create Your First Mesh**
   - Click "Create 3D Mesh"
   - A new plane will appear with your textures applied
   - The mesh will be displaced according to your depth map

5. **Fine-Tune Your Results**
   - Adjust Depth Strength to get desired height
   - Modify Subdivision Level for more/less detail
   - Adjust Smoothing Factor for desired surface finish
   - Modify material settings for desired appearance

### Tips and Best Practices

1. **Performance Optimization**
   - Start with lower subdivision levels
   - Increase only if needed
   - Keep image resolutions reasonable
   - Use PNG for depth maps (better precision)

2. **Quality Improvements**
   - Use high-contrast depth maps
   - Ensure depth maps are properly grayscale
   - Keep base image and depth map aligned
   - Test different smoothing values

3. **Common Workflows**
   - Architectural Details:
     1. Use lower depth strength
     2. Higher subdivision levels
     3. Lower smoothing factor
   
   - Landscape/Terrain:
     1. Higher depth strength
     2. Medium subdivision levels
     3. Higher smoothing factor

## Troubleshooting

**Problem**: Mesh appears flat
- Check depth map is proper grayscale
- Increase depth strength
- Verify depth map is loading correctly

**Problem**: Mesh is too angular
- Increase subdivision level
- Increase smoothing factor
- Check if auto-smooth is enabled

**Problem**: Performance issues
- Reduce subdivision level
- Use smaller textures
- Simplify the depth map

## Technical Requirements

- Blender 4.0 or newer
- Minimum 8GB RAM recommended
- Graphics card with 2GB VRAM or more recommended
- Supported operating systems:
  - Windows 10/11
  - macOS 10.15 or newer
  - Linux with compatible graphics drivers

---

For additional support or questions, please contact the addon creator through Blender Market or raise an issue on the project's repository.