# Ray Tracing in Python + OpenGL

This project implements a **real-time ray tracing** algorithm using **OpenGL (GLSL)** and **Python**. The implementation was inspired by *Sebastian Lague*'s video:  
[Ray Tracing in Unity](https://www.youtube.com/watch?v=Qz0KTGYJtUk)

## Description

- Renders **spheres** in a 3D environment with simplified global illumination.
- Supports reflections, emissive materials, glossy surfaces, and depth of field effects.
- Includes **tonemapping** and **gamma correction** for realistic display.

## Technologies Used

- Python (for OpenGL context setup and initialization)
- OpenGL / GLSL

## Features

- Ray tracing with multiple bounces (`MaxBounceCount`)
- Per-pixel sampling (`NumRaysPerPixel`) for anti-aliasing and soft shadows
- Environmental lighting + sun light support
- Depth of field via camera defocus blur
