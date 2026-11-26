"""Self-checks for the figures and animations (8 checks; skipped without matplotlib)."""
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from robot_soccer.environment.ball import BallParams
from robot_soccer.environment.pitch import PitchParams, goal_geometry
from robot_soccer.geometry import is_finite
from robot_soccer.robot.motion import RobotParams
from robot_soccer.sensors.params import SensorParams
from robot_soccer.simulations.demo_pitch_ball import demo_pitch_ball
from robot_soccer.simulations.demo_sensor import run_sensor_scenario
from robot_soccer.simulations.striker_keeper_drill import striker_keeper_drill

try:
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.figure import Figure
    from matplotlib.patches import Circle, Rectangle
    from PIL import Image
    from robot_soccer.visual.animation import DrillViewer, animate_sensor
    from robot_soccer.visual.pitch_view import draw_pitch
    from robot_soccer.visual.plots import (figure_pitch_ball_demo, figure_sensor_over_time,
                                           figure_sensor_top_view)
    HAVE_MATPLOTLIB = True
except ImportError:
    HAVE_MATPLOTLIB = False

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAVE_MATPLOTLIB, 'matplotlib is not installed')
class VisualChecks(unittest.TestCase):
    def test_1_pitch_drawing_matches_table_1(self):
        pp = PitchParams()
        ax = Figure().add_subplot()
        draw_pitch(ax, pp)
        polylines = {tuple(zip(map(float, ln.get_xdata()), map(float, ln.get_ydata()))) for ln in ax.lines}
        for s in (-1.0, 1.0):
            for depth, width in ((1.0, 3.0), (2.0, 5.0)):         # goal area, penalty area
                x0, x1 = s * 4.5, s * (4.5 - depth)
                self.assertIn(((x0, -width / 2), (x1, -width / 2), (x1, width / 2), (x0, width / 2)), polylines)
            self.assertIn(((s * 3.0, 0.0),), polylines)           # penalty mark
        self.assertIn(((0.0, -3.0), (0.0, 3.0)), polylines)       # halfway line
        for x1, y1, x2, y2 in goal_geometry(pp)[1]:
            self.assertIn(((x1, y1), (x2, y2)), polylines)        # nets
        circles = [p for p in ax.patches if isinstance(p, Circle)]
        self.assertIn(0.75, [c.radius for c in circles])          # centre circle
        self.assertEqual(sum(c.radius == pp.post_radius for c in circles), 4)
        rectangles = {(r.get_width(), r.get_height()) for r in ax.patches if isinstance(r, Rectangle)}
        self.assertEqual(rectangles, {(11.0, 8.0), (9.0, 6.0)})   # carpet and field

    def test_2_ball_demo_figure_shows_every_path(self):
        results = demo_pitch_ball(verbose=False)
        fig = figure_pitch_ball_demo(results, PitchParams(), BallParams())
        drawn = [ln for ln in fig.axes[0].lines if len(ln.get_xdata()) > 2 and ln.get_linewidth() == 2
                 and ln.get_linestyle() == '-' and len(ln.get_xdata()) != 4]
        lengths = sorted(len(ln.get_xdata()) for ln in drawn)
        self.assertEqual(lengths, sorted(len(r.path) for r in results))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'demo.png'
            fig.savefig(path)
            self.assertGreater(path.stat().st_size, 10000)

    def test_3_sensor_figures_show_the_recorded_data(self):
        world, sp, records = run_sensor_scenario()
        top = figure_sensor_top_view(records, world, sp).axes[0]
        n_seen = sum(r.percept.ball_visible for r in records)
        n_kept = sum(not r.percept.ball_visible and is_finite(r.percept.ball_pos) for r in records)
        dots = sorted(len(ln.get_xdata()) for ln in top.lines if ln.get_marker() == '.')
        self.assertEqual(dots, sorted((n_seen, n_kept)))
        over_time = figure_sensor_over_time(records)
        self.assertEqual(len(over_time.axes), 3)
        self.assertEqual(len(over_time.axes[0].lines[0].get_xdata()), len(records))

    def test_4_sensor_animation_saves_a_gif(self):
        world, sp, records = run_sensor_scenario()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sensor.gif'
            frames = animate_sensor(records[:100], world, sp, speed=1.0, save=str(path))
            with Image.open(path) as gif:
                self.assertEqual((frames, gif.n_frames), (20, 20))
                self.assertEqual(gif.info['duration'], 100)

    def test_5_sensor_animation_with_perfect_sensors(self):
        world, sp, records = run_sensor_scenario(mode='perfect')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'perfect.gif'
            self.assertEqual(animate_sensor(records[:50], world, sp, save=str(path)), 10)

    def test_6_drill_viewer_saves_a_gif_and_can_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'drill.gif'
            viewer = DrillViewer(2, [SensorParams()] * 3, RobotParams(), save=str(path))
            results = striker_keeper_drill(1, 'realistic', 3, n_attackers=2, verbose=False,
                                           on_step=lambda f: viewer(f) and f.t < 2.0)
            viewer.finish()
            self.assertEqual(results, [])                     # stopped before the attempt ended
            with Image.open(path) as gif:
                self.assertGreaterEqual(gif.n_frames, 20)

    def test_7_watching_does_not_change_the_results(self):
        plain = striker_keeper_drill(6, 'realistic', 5, n_attackers=2, verbose=False)
        watched = striker_keeper_drill(6, 'realistic', 5, n_attackers=2, verbose=False,
                                       on_step=lambda frame: True)
        self.assertEqual([asdict(a) for a in plain], [asdict(a) for a in watched])

    def test_8_simulation_runs_without_matplotlib(self):
        code = ('import sys; import robot_soccer.simulations.striker_keeper_drill, '
                'robot_soccer.simulations.compare_sensor_settings, robot_soccer.simulations.demo_sensor, '
                'robot_soccer.simulations.demo_pitch_ball, robot_soccer.simulations.animate_sensor; '
                "sys.exit('matplotlib' in sys.modules)")
        self.assertEqual(subprocess.run([sys.executable, '-c', code], cwd=ROOT).returncode, 0)


if __name__ == '__main__':
    unittest.main()
