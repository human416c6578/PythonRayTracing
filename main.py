import glfw
from OpenGL.GL import *
import numpy as np
import glm
import time

def load_shader(shader_type, shader_source):
    shader = glCreateShader(shader_type)
    glShaderSource(shader, shader_source)
    glCompileShader(shader)
    if glGetShaderiv(shader, GL_COMPILE_STATUS) != GL_TRUE:
        raise RuntimeError(glGetShaderInfoLog(shader).decode())
    return shader

def create_shader_program(vertex_path, fragment_path):
    with open(vertex_path, 'r') as f:
        vertex_src = f.read()
    with open(fragment_path, 'r') as f:
        fragment_src = f.read()

    vertex_shader = load_shader(GL_VERTEX_SHADER, vertex_src)
    fragment_shader = load_shader(GL_FRAGMENT_SHADER, fragment_src)

    program = glCreateProgram()
    glAttachShader(program, vertex_shader)
    glAttachShader(program, fragment_shader)
    glLinkProgram(program)
    if glGetProgramiv(program, GL_LINK_STATUS) != GL_TRUE:
        raise RuntimeError(glGetProgramInfoLog(program))
    return program

def create_texture(width, height):
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA32F, width, height, 0, GL_RGBA, GL_FLOAT, None)

    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    return tex

def create_fbo(texture):
    fbo = glGenFramebuffers(1)
    glBindFramebuffer(GL_FRAMEBUFFER, fbo)
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0)
    if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
        raise RuntimeError("Framebuffer not complete")
    return fbo

RayTracingMaterial_dtype = np.dtype([
    ('colour', np.float32, 4),
    ('emissionColour', np.float32, 4),
    ('specularColour', np.float32, 4),
    ('emissionStrength', np.float32),
    ('smoothness', np.float32),
    ('specularProbability', np.float32),
    ('flag', np.int32),
    #('_padding', np.int32),  # std140 requires padding to 16-byte alignment
])

Sphere_dtype = np.dtype([
    ('position', np.float32, 3),
    ('radius', np.float32),
    ('material', RayTracingMaterial_dtype)
])

# Quad vertices (fullscreen)
vertices = np.array([
    -1.0, -1.0, 0.0,
     1.0, -1.0, 0.0,
    -1.0,  1.0, 0.0,
     1.0,  1.0, 0.0,
], dtype=np.float32)

indices = np.array([0, 1, 2, 2, 1, 3], dtype=np.uint32)
width = 800
height = 800

# Init GLFW
glfw.init()
window = glfw.create_window(width, height, "Ray Tracing Shader", None, None)
glfw.make_context_current(window)

# Load shaders
shader = create_shader_program("shader.vert", "shader.frag")
accumul_shader = create_shader_program("shader.vert", "accumul_shader.frag")

# VBO/VAO setup
vao = glGenVertexArrays(1)
vbo = glGenBuffers(1)
ebo = glGenBuffers(1)

# Create texture to render scene to
render_texture = create_texture(width, height)
previous_texture = create_texture(width, height)

# Create framebuffer for rendering to the texture
fbo = create_fbo(render_texture)

glBindVertexArray(vao)

glBindBuffer(GL_ARRAY_BUFFER, vbo)
glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)

glEnableVertexAttribArray(0)
glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * 4, ctypes.c_void_p(0))

ubo = glGenBuffers(1)

spheres = np.array([
    #RED BALL
    ((0.0, 0.0, -5.0), 1.0,
     ((1.0, 0.1, 0.1, 0.1), (0.0, 0.0, 0.0, 0.0), (1.0, 1.0, 1.0, 1.0),
      1.0, 0.1, 0.0, 0)
    ),
    #MIRROR BALL
    ((2.0, 0.4, -3.0), 1.2,
     ((1.0, 1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 0.0), (1.0, 1.0, 1.0, 1.0),
      0.0, 1.0, 0.8, 0)
    ),
    #BLUE BALL
    ((5.0, -0.1, -3.0), 0.7,
     ((0.0, 1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 0.0), (0.4, 0.8, 0.8, 1.0),
      0.0, 1.0, 0.3, 0)
    ),
    #MIRROR BALL
    ((3.0, 2.0, -7.0), 2.0,
     ((1.0, 1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 0.0), (1.0, 1.0, 1.0, 1.0),
      0.0, 1.0, 1.0, 0)
    ),
    #FLOOR
    ((5.0, -51.5, -3.0), 50.7,
     ((1.0, 0.0, 1.0, 1.0), (0.7, 0.2, 0.2, 0.0), (1.0, 0.6, 1.0, 1.0),
      0.0, 0.2, 0.7, 0)
    ),
    #LIGHT
    ((7.0, 10.0, -3.0), 6.2,
     ((1.0, 1.0, 1.0, 1.0), (1.0, 1.0, 1.0, 1.0), (0.5, 0.5, 0.5, 1.0),
      2.8, 0.2, 0.5, 0)
    ),
], dtype=Sphere_dtype)


glBindBuffer(GL_UNIFORM_BUFFER, ubo)
glBufferData(GL_UNIFORM_BUFFER, spheres.nbytes, spheres, GL_STATIC_DRAW)

# === Uniforms ===
iResolutionLoc = glGetUniformLocation(shader, "iResolution")
ViewParamsLoc = glGetUniformLocation(shader, "ViewParams")
CamMatrixLoc = glGetUniformLocation(shader, "CamLocalToWorldMatrix")
CameraPosLoc = glGetUniformLocation(shader, "CameraPosition")
DivergeStrengthLoc = glGetUniformLocation(shader, "DivergeStrength")
DefocusStrengthLoc = glGetUniformLocation(shader, "DefocusStrength")
NumSpheresLoc = glGetUniformLocation(shader, "NumSpheres")
NumRaysPerPixelLoc = glGetUniformLocation(shader, "NumRaysPerPixel")
MaxBounceCountLoc = glGetUniformLocation(shader, "MaxBounceCount")
FrameCountLoc = glGetUniformLocation(shader, "FrameCount")

GroundColourLoc = glGetUniformLocation(shader, "GroundColour")
SkyColourHorizonLoc = glGetUniformLocation(shader, "SkyColourHorizon")
SkyColourZenithLoc = glGetUniformLocation(shader, "SkyColourZenith")
SunFocusLoc = glGetUniformLocation(shader, "SunFocus")
SunIntensityLoc = glGetUniformLocation(shader, "SunIntensity")
SunPositionLoc = glGetUniformLocation(shader, "SunPosition")


# === Camera setup ===
camera_position = glm.vec3(-3.2, 4, -7.5)
camera_front = glm.vec3(-0.73, 0.55, -0.4)
camera_up = glm.vec3(0, 1, 0)

yaw = -90.0
pitch = 0.0
last_x, last_y = 400, 400
first_mouse = True
cursor_disabled = False

# === Mouse callback ===
def mouse_callback(window, xpos, ypos):
    global yaw, pitch, last_x, last_y, first_mouse, camera_front

    if first_mouse:
        last_x = xpos
        last_y = ypos
        first_mouse = False

    xoffset = xpos - last_x
    yoffset = last_y - ypos  # reversed
    last_x = xpos
    last_y = ypos

    sensitivity = 0.1
    xoffset *= sensitivity
    yoffset *= sensitivity

    yaw -= xoffset
    pitch -= yoffset
    pitch = max(-89.0, min(89.0, pitch))

    front = glm.vec3(
        glm.cos(glm.radians(yaw)) * glm.cos(glm.radians(pitch)),
        glm.sin(glm.radians(pitch)),
        glm.sin(glm.radians(yaw)) * glm.cos(glm.radians(pitch))
    )
    camera_front = glm.normalize(front)

def mouse_button_callback(window, button, action, mods):
    global cursor_disabled
    if button == glfw.MOUSE_BUTTON_LEFT and action == glfw.PRESS and not cursor_disabled:
        glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_DISABLED)
        glfw.set_cursor_pos(window, 400, 400)  # Optional: re-center
        cursor_disabled = True

def key_callback(window, key, scancode, action, mods):
    global cursor_disabled
    if key == glfw.KEY_ESCAPE and action == glfw.PRESS and cursor_disabled:
        glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_NORMAL)
        cursor_disabled = False

glfw.set_cursor_pos_callback(window, mouse_callback)
glfw.set_mouse_button_callback(window, mouse_button_callback)
glfw.set_key_callback(window, key_callback)
#glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_DISABLED)

# === Time tracking ===s
start_time = time.time()
last_time = start_time

max_bounces = 7
rays_per_pixel = 15
frame = 0
prev_view_matrix = 0
FPS = 144
DivergeStrength = 1.2
DefocusStrength = 1.5

while not glfw.window_should_close(window):
    current_time = time.time()
    delta_time = current_time - last_time
    last_time = current_time
    elapsed = current_time - start_time

    width, height = glfw.get_framebuffer_size(window)

    glViewport(0, 0, width, height)
    glClear(GL_COLOR_BUFFER_BIT)

    # Camera movement (WASD)
    camera_speed = 5.5 * delta_time
    right = glm.normalize(glm.cross(camera_front, camera_up))

    if glfw.get_key(window, glfw.KEY_W) == glfw.PRESS:
        camera_position -= camera_speed * camera_front
    if glfw.get_key(window, glfw.KEY_S) == glfw.PRESS:
        camera_position += camera_speed * camera_front
    if glfw.get_key(window, glfw.KEY_A) == glfw.PRESS:
        camera_position -= right * camera_speed
    if glfw.get_key(window, glfw.KEY_D) == glfw.PRESS:
        camera_position += right * camera_speed
    if glfw.get_key(window, glfw.KEY_SPACE) == glfw.PRESS:
        camera_position += camera_up * camera_speed
    if glfw.get_key(window, glfw.KEY_LEFT_CONTROL) == glfw.PRESS:
        camera_position -= camera_up * camera_speed

    # Compute camera matrix
    view_matrix = glm.lookAt(camera_position, camera_position + camera_front, camera_up)
    cam_local_to_world = glm.inverse(view_matrix)

    if view_matrix != prev_view_matrix:
        frame = 0
    
    prev_view_matrix = view_matrix

    # Set uniforms for ray tracing shader
    glUseProgram(shader)
    glBindFramebuffer(GL_FRAMEBUFFER, fbo)

    glUniform2f(iResolutionLoc, width, height)
    glUniform3f(ViewParamsLoc, 1.0, 1.0, 1.0)
    glUniform3f(CameraPosLoc, *camera_position)
    glUniformMatrix4fv(CamMatrixLoc, 1, GL_FALSE, glm.value_ptr(cam_local_to_world))
    glUniform1f(DivergeStrengthLoc, DivergeStrength)
    glUniform1f(DefocusStrengthLoc, DefocusStrength)

    glUniform1i(NumSpheresLoc, len(spheres))
    glUniform1i(NumRaysPerPixelLoc, rays_per_pixel)
    glUniform1i(MaxBounceCountLoc, max_bounces)
    glUniform1i(FrameCountLoc, frame)

    glUniform4f(GroundColourLoc, 0.3, 0.25, 0.2, 1.0)         # Dark Brown
    glUniform4f(SkyColourHorizonLoc, 0.8, 0.6, 0.4, 1.0)      # Orange
    glUniform4f(SkyColourZenithLoc, 0.1, 0.3, 0.6, 1.0)       # Dark Blue
    glUniform1f(SunFocusLoc, 1.0)                             # Sharp sun
    glUniform1f(SunIntensityLoc, 0.2)
    glUniform3f(SunPositionLoc, -1.0, 0.7, -0.5)

    # Pass uniform block for spheres
    block_index = glGetUniformBlockIndex(shader, "SpheresBuffer")
    glUniformBlockBinding(shader, block_index, 0)
    glBindBufferBase(GL_UNIFORM_BUFFER, 0, ubo)

    glBindVertexArray(vao)
    glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)

    # Use the second shader to process the rendered texture
    glUseProgram(accumul_shader)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)  # Bind default framebuffer (the screen)
    glClear(GL_COLOR_BUFFER_BIT)

    glUniform1i(glGetUniformLocation(accumul_shader, "Frame"), frame)

    glActiveTexture(GL_TEXTURE0)
    glBindTexture(GL_TEXTURE_2D, render_texture)
    glUniform1i(glGetUniformLocation(accumul_shader, "MainTex"), 0)

    glActiveTexture(GL_TEXTURE1)
    glBindTexture(GL_TEXTURE_2D, previous_texture)
    glUniform1i(glGetUniformLocation(accumul_shader, "PrevTex"), 1)

    glBindVertexArray(vao)
    glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)

    glBindTexture(GL_TEXTURE_2D, previous_texture)
    glCopyTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 0, 0, width, height, 0)

    glfw.swap_buffers(window)
    glfw.poll_events()

    # Update frame counter
    frame += 1
    time.sleep(1.0 / FPS)

glfw.terminate()