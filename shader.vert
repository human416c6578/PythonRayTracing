#version 330 core
layout (location = 0) in vec3 aPos;
out vec2 uv;

void main()
{
    uv = aPos.xy * 0.5 + 0.5;
    gl_Position = vec4(aPos, 1.0);
}
