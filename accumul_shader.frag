#version 330 core

layout(location = 0) out vec4 FragColor;
in vec2 uv;

uniform sampler2D MainTex;
uniform sampler2D PrevTex;

uniform int Frame;

void main()
{
	vec4 col = texture(MainTex, uv);
	vec4 colPrev = texture(PrevTex, uv);
	float weight = 1.0 / (Frame + 1);

	vec4 accumulatedCol = clamp(colPrev * (1 - weight) + col * weight, 0.0, 1.0);

	FragColor = accumulatedCol;
}