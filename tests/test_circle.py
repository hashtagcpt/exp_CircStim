# monkey-patch pyglet shaders:
# ----------------------------

blend_mode_add = True
change_fbo_shader = True

if change_fbo_shader:
	fragFBOtoFramePatched = '''
    uniform sampler2D texture;

    float rand(vec2 seed){
        return fract(sin(dot(seed.xy ,vec2(12.9898,78.233))) * 43758.5453);
    }

    void main() {
        vec4 textureFrag = texture2D(texture,gl_TexCoord[0].st);
        gl_FragColor.rgb = textureFrag.rgb;
    }
    '''

	from psychopy import __version__ as psychopy_version
	from distutils.version import LooseVersion

	psychopy_version = LooseVersion(psychopy_version)

	if psychopy_version >= LooseVersion('1.84'):
	    from psychopy.visual import shaders
	else:
	    from psychopy import _shadersPyglet as shaders
	shaders.fragFBOtoFrame = fragFBOtoFramePatched

from psychopy import visual, event, core, monitors



# setup window
monitors = monitors.getAllMonitors()
if "BENQ-XL2411" in monitors:
	monitor = "BENQ-XL2411"
else:
	monitor = "testMonitor"
	print('BENQ monitor not found.')

if blend_mode_add:
    win = visual.Window(monitor=monitor, useFBO=True, blendMode='add')
else:
    win = visual.Window(monitor=monitor)
win.setMouseVisible(False)


def fix(win=win, color=(0.5, 0.5, 0.5), radius=0.15, edges=16):
	dot = visual.Circle(win, radius=radius, edges=edges, units='deg',
						interpolate=True)
	dot.setFillColor(color)
	dot.setLineColor(color)
	return dot

circle = fix(win, radius=0.18)

def show_circle():
	circle.draw()
	win.getMovieFrame('back')
	win.flip()
	event.waitKeys()


show_circle()
circle.edges = 8
show_circle()
circle.edges = 4
show_circle()

win.saveMovieFrames('test_circle.png')