#version 330 core

layout(location = 0) out vec4 FragColor;
in vec2 uv;

uniform vec2 iResolution;

uniform vec3 ViewParams;
uniform mat4 CamLocalToWorldMatrix;
uniform vec3 CameraPosition;
uniform float DivergeStrength;
uniform float DefocusStrength;

uniform int NumSpheres;
uniform int NumRaysPerPixel;
uniform int MaxBounceCount;
uniform int FrameCount;

uniform vec4 GroundColour;
uniform vec4 SkyColourHorizon;
uniform vec4 SkyColourZenith;
uniform float SunFocus;
uniform float SunIntensity;
uniform vec3 SunPosition;

struct Ray {
    vec3 origin;
    vec3 dir;
};

struct RayTracingMaterial
{
	vec4 colour;
	vec4 emissionColour;
	vec4 specularColour;
	float emissionStrength;
	float smoothness;
	float specularProbability;
	int flag;
};

struct HitInfo
{
    bool didHit;
    float dst;
    vec3 hitPoint;
    vec3 normal;
    RayTracingMaterial material;
};

struct Sphere
{
    vec3 position;
    float radius;
    RayTracingMaterial material;
};

layout(std140) uniform SpheresBuffer 
{
    Sphere Spheres[10];
};

#define EPSILON 0.0001
#define PI 3.14159265359

vec4 lerp(vec4 a, vec4 b, float t) {
    return a + t * (b - a);
}

vec3 GetEnvironmentLight(Ray ray)
{
    float skyGradientT = pow(smoothstep(0.0, 0.4, ray.dir.y), 0.35);
    float groundToSkyT = smoothstep(-0.01, 0.0, ray.dir.y);

    vec4 skyGradient = lerp(SkyColourHorizon, SkyColourZenith, skyGradientT);
    float sun = pow(max(0.0, dot(ray.dir, SunPosition)), SunFocus) * SunIntensity;

    vec4 composite = lerp(GroundColour, skyGradient, groundToSkyT);
    return composite.rgb + sun * float(groundToSkyT >= 1.0);
}


uint NextRandom(inout uint state)
{
    state = state * 747796405u + 2891336453u;
    uint result = ((state >> ((state >> 28) + 4u)) ^ state) * 277803737u;
    result = (result >> 22u) ^ result;
    return result;
}

float RandomValue(inout uint state)
{
    return NextRandom(state) / 4294967295.0;
}

vec2 RandomPointInCircle(inout uint rngState)
{
    float angle = RandomValue(rngState) * 2 * PI;
    vec2 pointOnCircle = vec2(cos(angle), sin(angle));

    return pointOnCircle * sqrt(RandomValue(rngState));
}

float RandomValueNormalDistribution(inout uint state)
{
    float theta = 2 * PI * RandomValue(state);
    float rho = sqrt(-2 * log(RandomValue(state)));
    return rho * cos(theta);
}

vec3 RandomDirection(inout uint state)
{
    float x = RandomValueNormalDistribution(state);
    float y = RandomValueNormalDistribution(state);
    float z = RandomValueNormalDistribution(state);

    return normalize(vec3(x, y, z));
}

vec3 RandomHemisphereDirection(vec3 normal, inout uint rngState)
{
    vec3 dir = RandomDirection(rngState);
    return dir * sign(dot(normal, dir));
}

HitInfo RaySphere(Ray ray, vec3 sphereCenter, float radius) 
{

    HitInfo hitInfo;
    hitInfo.didHit = false;
    hitInfo.dst = 1.0 / 0.0;  // Represent infinity

    vec3 offsetRayOrigin = ray.origin - sphereCenter;

    float a = dot(ray.dir, ray.dir);
    float b = 2 * dot(offsetRayOrigin, ray.dir);
    float c = dot(offsetRayOrigin, offsetRayOrigin) - (radius * radius);
    float discriminant = b * b - 4 * a * c;

    if (discriminant > 0.0) {
        float dst = (-b - sqrt(discriminant)) / (2 * a);

        if (dst >= 0) {  // Prevent self-intersection
            hitInfo.didHit = true;
            hitInfo.dst = dst;
            hitInfo.hitPoint = ray.origin + ray.dir * dst;
            hitInfo.normal = normalize(hitInfo.hitPoint - sphereCenter);
        }
    }
    return hitInfo;
}

HitInfo CalculateRayCollision(Ray ray) 
{
    HitInfo closestHit;
    closestHit.didHit = false;
    closestHit.dst = 1.0 / 0.0;  // infinity

    for (int i = 0; i < NumSpheres; i++) {
        Sphere sphere = Spheres[i];  // Access sphere from UBO
        HitInfo hitInfo = RaySphere(ray, sphere.position, sphere.radius);

        if (hitInfo.didHit && hitInfo.dst < closestHit.dst) {
            closestHit = hitInfo;
            closestHit.material = sphere.material;  // Store the material
        }
    }

    return closestHit;
}

vec3 Trace(Ray ray, inout uint rngState)
{
    vec3 incomingLight = vec3(0);
    vec3 rayColour = vec3(1.0);

    for(int i = 0;i <= MaxBounceCount;i++)
    {
        HitInfo hitInfo = CalculateRayCollision(ray);
        if(hitInfo.didHit)
        {
            //ray.origin = hitInfo.hitPoint;
            ray.origin = hitInfo.hitPoint + hitInfo.normal * EPSILON;
            RayTracingMaterial material = hitInfo.material;

            vec3 diffuseDir = normalize(hitInfo.normal + RandomDirection(rngState));
            vec3 specularDir = reflect(ray.dir, hitInfo.normal);
            bool isSpecularBounce = material.specularProbability >= RandomValue(rngState);
            ray.dir = vec3(lerp(vec4(diffuseDir, 1.0), vec4(specularDir, 1.0), material.smoothness * float(isSpecularBounce)));
            
            vec3 emittedLight = vec3(material.emissionColour) * material.emissionStrength;
            incomingLight += emittedLight * rayColour;

            rayColour *= vec3(lerp(material.colour, material.specularColour, float(isSpecularBounce)));
        }
        else
        {
            incomingLight += GetEnvironmentLight(ray) * rayColour;
            break;
        }
    }

    return incomingLight;
}

void main() {
    // Convert screen UV to camera local space
    vec3 viewPointLocal = vec3(uv - 0.5, 1.0) * ViewParams;

    // Transform to world space
    vec4 viewPointWorld = CamLocalToWorldMatrix * vec4(viewPointLocal, 1.0);
    vec3 camRight = CamLocalToWorldMatrix[0].xyz;
    vec3 camUp    = CamLocalToWorldMatrix[1].xyz;

    vec2 numPixels = iResolution.xy;
    vec2 pixelCoord = uv * numPixels;
    uint pixelIndex = uint(pixelCoord.y * numPixels.x + pixelCoord.x);
    uint randomState = pixelIndex + uint(FrameCount) * 719393u;
    
    vec3 totalIncomingLight = vec3(0.0);

    Ray ray;
    
    for(int rayIndex = 0;rayIndex <= NumRaysPerPixel; rayIndex++)
    {
        vec2 defocusJitter = RandomPointInCircle(randomState) * DefocusStrength / numPixels.x;
        ray.origin = CameraPosition + camRight * defocusJitter.x + camUp * defocusJitter.y;

        vec2 jitter = RandomPointInCircle(randomState) * DivergeStrength / numPixels.x;
        vec3 jitterFocusPoint = vec3(viewPointWorld) + camRight * jitter.x * camUp * jitter.y;
        ray.dir = normalize(vec3(jitterFocusPoint) - ray.origin);
        /*
        ray.origin = CameraPosition;
        ray.dir = normalize(vec3(viewPointWorld) - ray.origin);
         */
        totalIncomingLight += Trace(ray, randomState);
    }

    vec3 pixelCol = totalIncomingLight / NumRaysPerPixel;

    vec3 tonemapped = pixelCol / (pixelCol + vec3(1.0)); // Reinhard
    vec3 gammaCorrected = pow(tonemapped, vec3(1.0 / 2.2));
    FragColor = vec4(gammaCorrected, 1.0);
    //FragColor = vec4(pixelCol, 1.0);
}

