// GMEM restore reproducer: small offscreen FBO (colour + depth/stencil) that
// is drawn into repeatedly without clearing, so freedreno must reload (restore)
// colour and depth/stencil into GMEM every frame. Mirrors gnome-shell's
// offscreen panel target (about 1080x110 with a packed depth/stencil buffer).
// usage: gmemrepro [frames] [w] [h] [mode]   mode: 0 depth24s8 rb, 1 depth tex, 2 stencil-clip
// Build: cc -O2 -o gmemrepro gmemrepro.c -lEGL -lGLESv2
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <stdio.h>
#include <stdlib.h>

static GLuint prog(void)
{
	const char *vs = "#version 300 es\nin vec2 p; uniform float o;"
			 "void main(){gl_Position=vec4(p.x*0.9+o,p.y*0.9,0.5*p.x,1.0);}";
	const char *fs = "#version 300 es\nprecision mediump float; uniform float o; out vec4 c;"
			 "void main(){c=vec4(o,0.5,1.0-o,1.0);}";
	GLuint v = glCreateShader(GL_VERTEX_SHADER), f = glCreateShader(GL_FRAGMENT_SHADER), p;
	glShaderSource(v, 1, &vs, NULL); glCompileShader(v);
	glShaderSource(f, 1, &fs, NULL); glCompileShader(f);
	p = glCreateProgram(); glAttachShader(p, v); glAttachShader(p, f);
	glBindAttribLocation(p, 0, "p"); glLinkProgram(p);
	return p;
}

int main(int argc, char **argv)
{
	int frames = argc > 1 ? atoi(argv[1]) : 600;
	int w = argc > 2 ? atoi(argv[2]) : 1080, h = argc > 3 ? atoi(argv[3]) : 110;
	int mode = argc > 4 ? atoi(argv[4]) : 0;
	PFNEGLGETPLATFORMDISPLAYEXTPROC gpd =
		(void *)eglGetProcAddress("eglGetPlatformDisplayEXT");
	EGLDisplay d = gpd(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, NULL);
	EGLint maj, min, n; EGLConfig cfg;
	if (!eglInitialize(d, &maj, &min)) { puts("eglInitialize failed"); return 1; }
	EGLint ca[] = { EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT, EGL_NONE };
	eglChooseConfig(d, ca, &cfg, 1, &n);
	eglBindAPI(EGL_OPENGL_ES_API);
	EGLint xa[] = { EGL_CONTEXT_MAJOR_VERSION, 3, EGL_NONE };
	EGLContext c = eglCreateContext(d, cfg, EGL_NO_CONTEXT, xa);
	eglMakeCurrent(d, EGL_NO_SURFACE, EGL_NO_SURFACE, c);
	printf("renderer %s\n", glGetString(GL_RENDERER));

	GLuint fb, tex, ds;
	glGenFramebuffers(1, &fb); glBindFramebuffer(GL_FRAMEBUFFER, fb);
	glGenTextures(1, &tex); glBindTexture(GL_TEXTURE_2D, tex);
	glTexStorage2D(GL_TEXTURE_2D, 1, GL_RGBA8, w, h);
	glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, tex, 0);
	if (mode == 1) {
		glGenTextures(1, &ds); glBindTexture(GL_TEXTURE_2D, ds);
		glTexStorage2D(GL_TEXTURE_2D, 1, GL_DEPTH24_STENCIL8, w, h);
		glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_TEXTURE_2D, ds, 0);
	} else {
		glGenRenderbuffers(1, &ds); glBindRenderbuffer(GL_RENDERBUFFER, ds);
		glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, w, h);
		glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER, ds);
	}
	if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) { puts("fbo incomplete"); return 1; }
	glViewport(0, 0, w, h);
	glClearColor(0, 0, 0, 1); glClearDepthf(1); glClearStencil(0);
	glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT | GL_STENCIL_BUFFER_BIT);

	GLuint p = prog(); glUseProgram(p);
	GLint uo = glGetUniformLocation(p, "o");
	float q[] = { -1, -1, 1, -1, -1, 1, 1, 1 };
	GLuint vb; glGenBuffers(1, &vb); glBindBuffer(GL_ARRAY_BUFFER, vb);
	glBufferData(GL_ARRAY_BUFFER, sizeof q, q, GL_STATIC_DRAW);
	glEnableVertexAttribArray(0); glVertexAttribPointer(0, 2, GL_FLOAT, 0, 0, 0);
	glEnable(GL_DEPTH_TEST); glDepthFunc(GL_LEQUAL);
	if (mode == 2) { glEnable(GL_STENCIL_TEST); }

	unsigned char px[4];
	for (int i = 0; i < frames; i++) {
		glBindFramebuffer(GL_FRAMEBUFFER, fb);
		if (mode == 2) {
			/* clip: write a stencil rectangle, then draw where stencil == 1 */
			glStencilFunc(GL_ALWAYS, 1, 0xff); glStencilOp(GL_KEEP, GL_KEEP, GL_REPLACE);
			glColorMask(0, 0, 0, 0); glUniform1f(uo, 0.0f); glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
			glColorMask(1, 1, 1, 1); glStencilFunc(GL_EQUAL, 1, 0xff); glStencilOp(GL_KEEP, GL_KEEP, GL_KEEP);
		}
		glUniform1f(uo, (i % 20) / 40.0f);
		glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
		/* read back forces the batch to flush; the next frame must restore */
		glReadPixels(i % w, 0, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, px);
	}
	glFinish();
	printf("done %d frames %dx%d mode %d last px %d,%d,%d\n", frames, w, h, mode, px[0], px[1], px[2]);
	return 0;
}
