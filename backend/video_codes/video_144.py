from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.azure import AzureService
import numpy as np

import base64 as _b64_svg, os as _os

_SVG_DATA = {
    "thermometer": "PHN2ZyB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8Y2lyY2xlIGN4PSI1MCIgY3k9IjgwIiByPSIxMCIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyLjUiLz4KICA8cGF0aCBkPSJNIDQ0IDcwIEwgNDQgMjAgUSA0NCAxNSA1MCAxNSBRIDU2IDE1IDU2IDIwIEwgNTYgNzAiIHN0cm9rZT0id2hpdGUiIGZpbGw9Im5vbmUiIHN0cm9rZS13aWR0aD0iMi41Ii8+CiAgPGxpbmUgeDE9IjQ0IiB5MT0iNzAiIHgyPSI1NiIgeTI9IjcwIiBzdHJva2U9IndoaXRlIiBmaWxsPSJub25lIiBzdHJva2Utd2lkdGg9IjIuNSIvPgogIDxsaW5lIHgxPSI0NiIgeTE9IjQ1IiB4Mj0iNTQiIHkyPSI0NSIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyLjUiLz4KICA8bGluZSB4MT0iNDYiIHkxPSIzNSIgeDI9IjUyIiB5Mj0iMzUiIHN0cm9rZT0id2hpdGUiIGZpbGw9Im5vbmUiIHN0cm9rZS13aWR0aD0iMiIvPgogIDxsaW5lIHgxPSI0NiIgeTE9IjU1IiB4Mj0iNTIiIHkyPSI1NSIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyIi8+Cjwvc3ZnPg=="
}

def get_svg(name, url=None, height=0.8):
    """Write inline SVG to /tmp and return as a sized SVGMobject."""
    tmp = f"/tmp/svg_{name}.svg"
    if not _os.path.exists(tmp):
        if name in _SVG_DATA:
            with open(tmp, 'wb') as _f:
                _f.write(_b64_svg.b64decode(_SVG_DATA[name]))
        elif url:
            import urllib.request
            urllib.request.urlretrieve(url, tmp)
    return SVGMobject(tmp).set_height(height)


class KineticTheoryOfMatter(VoiceoverScene):
    def show_subtitle(self, text, duration=None):
        import textwrap
        wrapped = "\n".join(textwrap.wrap(text, width=60))
        subtitle = Text(wrapped, font_size=18, color=WHITE, line_spacing=1.2).to_edge(DOWN, buff=0.3)
        self.play(FadeIn(subtitle))
        if duration:
            self.wait(duration)
        return subtitle

    def construct(self):
        self.set_speech_service(AzureService(voice="en-US-JennyNeural", global_speed=1.0))
        self.camera.background_color = ManimColor("#0D1117")

        # ═══ SETUP BLOCK: define every object used before any voiceover block ═══
        rng = np.random.default_rng(42)

        ACCENT = ManimColor("#FF6B6B")
        NEUTRAL = ManimColor("#4ECDC4")
        WARM = ManimColor("#FFA500")
        HOT = ManimColor("#FF4500")
        COLD = ManimColor("#4FC3F7")
        EQUAL = ManimColor("#B39DDB")

        def rand_pt(half=1.3):
            return np.array([rng.uniform(-half, half), rng.uniform(-half, half), 0.0])

        def rand_dir():
            v = np.array([rng.uniform(-1, 1), rng.uniform(-1, 1), 0.0])
            n = np.linalg.norm(v)
            return v / n if n > 1e-6 else np.array([1.0, 0.0, 0.0])

        title = Text("Kinetic Theory of Matter", font_size=40).to_edge(UP)

        # --- Phase 1: marbles ---
        ground = Line(LEFT * 6, RIGHT * 6, color=GREY).shift(DOWN * 1.5)
        marble_A = Dot(point=np.array([-3.5, -1.15, 0]), radius=0.25, color=NEUTRAL)
        groupA = VGroup(marble_A)
        marble_B = Dot(point=np.array([3.5, -1.15, 0]), radius=0.25, color=WARM)
        groupB = VGroup(marble_B)
        label_A = Text("A", font_size=24).next_to(groupA, UP, buff=0.15)
        label_B = Text("B", font_size=24).next_to(groupB, UP, buff=0.15)
        vA = Arrow(start=groupA.get_center(), end=groupA.get_center() + RIGHT * 1.0, buff=0, color=NEUTRAL)
        vB = Arrow(start=groupB.get_center(), end=groupB.get_center() + LEFT * 1.0, buff=0, color=WARM)
        collide_caption = Text("Collision transfers energy", font_size=28, color=ACCENT).move_to(DOWN * 2.2)

        # --- Phase 2: solid ---
        solid_box = Square(side_length=3.2, color=GREY_B).move_to(ORIGIN)
        xs = [-0.9, 0.0, 0.9]
        ys = [-0.9, 0.0, 0.9]
        solid_positions = [np.array([x, y, 0]) for y in ys for x in xs]
        solid_dots = VGroup(*[Dot(point=p, radius=0.12, color=HOT) for p in solid_positions])
        solid_homes = [d.get_center().copy() for d in solid_dots]

        def idx(i, j):
            return i * 3 + j

        solid_edges = []
        for i in range(3):
            for j in range(3):
                if j < 2:
                    solid_edges.append((idx(i, j), idx(i, j + 1)))
                if i < 2:
                    solid_edges.append((idx(i, j), idx(i + 1, j)))
        solid_bonds = VGroup(*[Line(solid_positions[a], solid_positions[b], color=GREY, stroke_width=1.5)
                               for a, b in solid_edges])
        solid_label = Text("Solid", font_size=28).next_to(solid_box, DOWN, buff=0.3)
        solid_group = VGroup(solid_box, solid_dots, solid_bonds, solid_label)
        vib_arrow = Arrow(start=solid_box.get_top() + UP * 0.1, end=solid_box.get_top() + UP * 0.6, color=ACCENT)
        solid_caption = Text("Particles vibrate but stay in place", font_size=26, color=ACCENT).move_to(DOWN * 2.5)

        # --- Phase 3: liquid ---
        liq_box = Square(side_length=3.2, color=GREY_B).move_to(ORIGIN)
        liq_positions = [rand_pt(1.3) for _ in range(10)]
        liquid_dots = VGroup(*[Dot(point=p, radius=0.12, color=NEUTRAL) for p in liq_positions])
        _s, _e = liq_box.get_corner(UL), liq_box.get_corner(UR)
        if np.linalg.norm(_e - _s) > 0.01:
            surface_dash = DashedLine(_s, _e, color=BLUE_B)
        else:
            surface_dash = DashedLine(_s, _s + RIGHT * 0.1, color=BLUE_B)
        liq_label = Text("Liquid", font_size=28).next_to(liq_box, DOWN, buff=0.3)
        liquid_group = VGroup(liq_box, liquid_dots, surface_dash, liq_label)
        tracer = liquid_dots[0]

        liq_paths = []
        for d in liquid_dots:
            start = d.get_center().copy()
            end = rand_pt(1.3)
            while np.linalg.norm(end - start) < 0.3:
                end = rand_pt(1.3)
            liq_paths.append(Line(start, end))

        liq_paths2 = []
        for p in liq_paths:
            start = p.get_end().copy()
            end = rand_pt(1.3)
            while np.linalg.norm(end - start) < 0.3:
                end = rand_pt(1.3)
            liq_paths2.append(Line(start, end))

        liq_caption = Text("Particles slide past each other", font_size=26, color=ACCENT).move_to(DOWN * 2.5)

        # --- Phase 4: gas ---
        gas_box = Square(side_length=3.4, color=GREY_B).move_to(ORIGIN)
        gas_positions = [rand_pt(1.4) for _ in range(8)]
        gas_dots = VGroup(*[Dot(point=p, radius=0.1, color=WARM) for p in gas_positions])
        gas_label = Text("Gas", font_size=28).next_to(gas_box, DOWN, buff=0.3)
        gas_group = VGroup(gas_box, gas_dots, gas_label)
        gas_arrows = VGroup(*[Arrow(start=p, end=p + rand_dir() * 0.5, buff=0, color=WARM, stroke_width=3)
                              for p in gas_positions])
        gas_seeds = [p.copy() for p in gas_positions]
        gas_targets1 = [rand_pt(1.4) for _ in range(8)]
        gas_targets2 = [rand_pt(1.4) for _ in range(8)]
        gas_caption = Text("Fast, energetic collisions", font_size=26, color=ACCENT).move_to(DOWN * 2.5)

        # --- Phase 5: heat transfer ---
        cold_box = Square(side_length=2.4, color=GREY_B).move_to(np.array([3.4, 0, 0]))
        cold_positions = [rand_pt(0.9) + np.array([3.4, 0, 0]) for _ in range(6)]
        cold_dots = VGroup(*[Dot(point=p, radius=0.1, color=COLD) for p in cold_positions])
        cold_label = Text("Cold", font_size=24).next_to(cold_box, DOWN, buff=0.2)
        cold_group = VGroup(cold_box, cold_dots, cold_label)

        left_therm = get_svg("thermometer", height=1.0).move_to(np.array([-3.4, 2.0, 0]))
        right_therm = get_svg("thermometer", height=1.0).move_to(np.array([3.4, 2.0, 0]))
        left_col = Rectangle(width=0.3, height=0.6, color=HOT, fill_opacity=1).move_to(np.array([-3.4, 1.3, 0]))
        right_col = Rectangle(width=0.3, height=0.2, color=COLD, fill_opacity=1).move_to(np.array([3.4, 1.15, 0]))

        heat_arrow = Arrow(start=np.array([-1.6, 0, 0]), end=np.array([1.6, 0, 0]), color=ACCENT, buff=0.1)
        q_label = Text("Q", font_size=32, color=ACCENT).next_to(heat_arrow, UP, buff=0.15)

        packets = VGroup(*[Dot(radius=0.08, color=ACCENT).move_to(heat_arrow.get_start()) for _ in range(4)])
        _ps, _pe = heat_arrow.get_start(), heat_arrow.get_end()
        if np.linalg.norm(_pe - _ps) > 0.01:
            packet_path = Line(_ps, _pe)
        else:
            packet_path = Line(_ps, _ps + RIGHT * 0.1)

        # --- Phase 6: equalization ---
        left_num = DecimalNumber(90, num_decimal_places=0, font_size=28, color=HOT).next_to(left_therm, DOWN, buff=0.2)
        right_num = DecimalNumber(10, num_decimal_places=0, font_size=28, color=COLD).next_to(right_therm, DOWN, buff=0.2)
        headline = Text("Thermal Equilibrium Reached", font_size=30, color=EQUAL).move_to(UP * 2.3)

        # --- Phase 7: final ---
        soft_ground = Line(LEFT * 6, RIGHT * 6, color=GREEN_D).shift(DOWN * 2.5)
        final_marble_positions = [np.array([-2.5, -2.15, 0]), np.array([-0.8, -2.15, 0]),
                                   np.array([0.8, -2.15, 0]), np.array([2.5, -2.15, 0])]
        final_marbles = VGroup(*[Dot(point=p, radius=0.2, color=c)
                                  for p, c in zip(final_marble_positions, [NEUTRAL, WARM, HOT, COLD])])
        final_line = Text("Matter's states, driven by particle collisions.",
                           font_size=26, color=WHITE).move_to(UP * 1.3)

        self.add(title)
        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Imagine two marbles rolling towards each other. What happens when they collide?") as tracker:
            sub = self.show_subtitle("Imagine two marbles rolling towards each other. What happens when they collide?")
            self.play(FadeIn(ground, shift=UP * 0.3), run_time=1.0, rate_func=smooth)
            self.play(AnimationGroup(FadeIn(groupA, shift=RIGHT * 0.8), FadeIn(groupB, shift=LEFT * 0.8), lag_ratio=0.3), run_time=1.8, rate_func=smooth)
            self.play(FadeIn(label_A, shift=UP * 0.2), FadeIn(label_B, shift=UP * 0.2), run_time=1.0, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 4.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="One slows down, and the other speeds up.") as tracker:
            sub = self.show_subtitle("One slows down, and the other speeds up.")
            self.play(AnimationGroup(GrowArrow(vA), GrowArrow(vB), lag_ratio=0.25), run_time=1.2, rate_func=smooth)
            self.play(groupA.animate.move_to(np.array([-0.55, -1.15, 0])), vA.animate.shift(RIGHT * 3.45),
                      groupB.animate.move_to(np.array([0.55, -1.15, 0])), vB.animate.shift(LEFT * 3.45),
                      label_A.animate.shift(RIGHT * 3.45), label_B.animate.shift(LEFT * 3.45),
                      run_time=1.6, rate_func=rush_into)
            self.play(Flash(DOWN * 1.15, line_length=0.5, num_lines=14, color=ACCENT), run_time=0.6)
            self.play(groupA.animate.move_to(np.array([-2.2, -1.15, 0])).set_color(NEUTRAL), vA.animate.scale(0.55).shift(LEFT * 1.65),
                      groupB.animate.move_to(np.array([3.6, -1.15, 0])).set_color(WARM), vB.animate.rotate(PI).scale(2.0).shift(RIGHT * 3.05),
                      label_A.animate.shift(LEFT * 1.65), label_B.animate.shift(RIGHT * 3.05),
                      run_time=1.8, rate_func=rush_from)
            self.play(FadeIn(collide_caption, shift=UP * 0.2), run_time=1.0, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 6.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Now, think of particles in a solid. They're like marbles stuck in place, just vibrating.") as tracker:
            sub = self.show_subtitle("Now, think of particles in a solid. They're like marbles stuck in place, just vibrating.")
            self.play(FadeOut(groupA, groupB, vA, vB, label_A, label_B, collide_caption, ground, shift=DOWN * 0.5), run_time=0.8, rate_func=rush_into)
            self.play(Create(solid_box), run_time=1.2, rate_func=linear)
            self.play(FadeIn(solid_dots, shift=UP * 0.4, lag_ratio=0.06), run_time=2.0, rate_func=smooth)
            self.play(DrawBorderThenFill(solid_bonds), run_time=1.5)
            self.play(FadeIn(solid_label, shift=DOWN * 0.3), run_time=0.8, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 6.8))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="When they collide, they transfer energy, but they don't move far.") as tracker:
            sub = self.show_subtitle("When they collide, they transfer energy, but they don't move far.")
            self.play(AnimationGroup(*[Indicate(d, scale_factor=1.25, color=ACCENT) for d in solid_dots], lag_ratio=0.05), run_time=1.4)
            self.play(GrowFromCenter(vib_arrow), run_time=0.6)
            for _ in range(2):
                self.play(*[d.animate.shift(np.array([rng.uniform(-0.07, 0.07), rng.uniform(-0.07, 0.07), 0])) for d in solid_dots],
                          run_time=0.9, rate_func=there_and_back)
            self.play(*[d.animate.move_to(h) for d, h in zip(solid_dots, solid_homes)], run_time=0.6, rate_func=smooth)
            self.play(FadeIn(solid_caption, shift=UP * 0.2), run_time=1.0, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 6.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="In a liquid, particles are closer but can slide past each other.") as tracker:
            sub = self.show_subtitle("In a liquid, particles are closer but can slide past each other.")
            self.play(FadeOut(vib_arrow, solid_caption, shift=DOWN * 0.3), solid_group.animate.set_opacity(0.6), run_time=0.8, rate_func=rush_into)
            self.play(Create(liq_box), run_time=1.0, rate_func=smooth)
            self.play(FadeIn(liquid_dots, shift=UP * 0.5, lag_ratio=0.08), run_time=2.0, rate_func=smooth)
            self.play(DrawBorderThenFill(surface_dash), run_time=0.8)
            self.play(FadeIn(liq_label, shift=DOWN * 0.3), run_time=0.7, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 5.8))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Collisions here can change their speed and direction.") as tracker:
            sub = self.show_subtitle("Collisions here can change their speed and direction.")
            self.play(tracer.animate.set_color(ACCENT).scale(1.2), run_time=0.6, rate_func=smooth)
            self.play(AnimationGroup(*[MoveAlongPath(d, p) for d, p in zip(liquid_dots, liq_paths)], lag_ratio=0.25),
                      run_time=3.0, rate_func=smooth)
            self.play(AnimationGroup(*[MoveAlongPath(d, p) for d, p in zip(liquid_dots, liq_paths2)], lag_ratio=0.15),
                      run_time=2.4, rate_func=smooth)
            self.play(FadeIn(liq_caption, shift=UP * 0.2), run_time=1.0, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 7.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="In a gas, particles are far apart and move quickly.") as tracker:
            sub = self.show_subtitle("In a gas, particles are far apart and move quickly.")
            self.play(FadeOut(liq_caption, shift=DOWN * 0.3), liquid_group.animate.set_opacity(0.6), run_time=0.7, rate_func=rush_into)
            self.play(Create(gas_box), run_time=1.0, rate_func=smooth)
            self.play(FadeIn(gas_dots, shift=UP * 0.6, scale=0.6, lag_ratio=0.1), run_time=2.2, rate_func=smooth)
            self.play(FadeIn(gas_label, shift=DOWN * 0.3), run_time=0.7, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 4.8))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Collisions can significantly change their speed and direction.") as tracker:
            sub = self.show_subtitle("Collisions can significantly change their speed and direction.")
            self.play(AnimationGroup(*[GrowArrow(a) for a in gas_arrows], lag_ratio=0.25), run_time=1.5)
            self.play(*[d.animate.move_to(t) for d, t in zip(gas_dots, gas_targets1)],
                      *[a.animate.shift(t - s) for a, t, s in zip(gas_arrows, gas_targets1, gas_seeds)],
                      run_time=1.8, rate_func=linear)
            self.play(Flash(gas_box.get_right(), line_length=0.25, color=ACCENT), run_time=0.4)
            self.play(*[d.animate.move_to(t) for d, t in zip(gas_dots, gas_targets2)],
                      *[a.animate.rotate(PI).shift(t - s) for a, t, s in zip(gas_arrows, gas_targets2, gas_targets1)],
                      run_time=1.8, rate_func=linear)
            self.play(FadeIn(gas_caption, shift=UP * 0.2), run_time=1.0, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 7.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="When a fast particle hits a slower one, it transfers energy, slowing down itself and speeding up the other.") as tracker:
            sub = self.show_subtitle("When a fast particle hits a slower one, it transfers energy, slowing down itself and speeding up the other.")
            self.play(FadeOut(liquid_group, gas_group, gas_arrows, gas_caption, solid_bonds, shift=DOWN * 0.4), run_time=0.8, rate_func=rush_into)
            self.play(solid_group.animate.set_opacity(1.0).move_to(np.array([-3.4, 0, 0])).scale(0.8),
                      solid_dots.animate.set_color(HOT), run_time=1.2, rate_func=smooth)
            self.play(FadeIn(cold_group, shift=LEFT * 0.4), FadeIn(left_therm, shift=RIGHT * 0.2), FadeIn(right_therm, shift=RIGHT * 0.2),
                      FadeIn(left_col), FadeIn(right_col), run_time=1.2, rate_func=smooth)
            self.play(GrowArrow(heat_arrow), run_time=1.2)
            self.play(FadeIn(q_label, shift=UP * 0.2), run_time=0.6, rate_func=smooth)
            self.play(Circumscribe(heat_arrow, color=ACCENT, buff=0.15), run_time=1.2)
            self.play(AnimationGroup(*[MoveAlongPath(p, packet_path) for p in packets], lag_ratio=0.25),
                      run_time=2.4, rate_func=smooth)
            self.play(FadeOut(packets), Indicate(q_label, scale_factor=1.8, color=ACCENT), run_time=1.0)
            self.wait(max(0.1, tracker.duration - 10.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So, collisions transfer kinetic energy, affecting particle speeds differently in solids, liquids, and gases.") as tracker:
            sub = self.show_subtitle("So, collisions transfer kinetic energy, affecting particle speeds differently in solids, liquids, and gases.")
            self.play(FadeIn(left_num, shift=DOWN * 0.2), FadeIn(right_num, shift=DOWN * 0.2), run_time=0.8, rate_func=smooth)
            self.play(left_num.animate.set_value(50), right_num.animate.set_value(50),
                      left_col.animate.stretch_to_fit_height(0.95, about_edge=DOWN).set_color(EQUAL),
                      right_col.animate.stretch_to_fit_height(0.95, about_edge=DOWN).set_color(EQUAL),
                      left_therm.animate.set_color(EQUAL), right_therm.animate.set_color(EQUAL),
                      solid_dots.animate.set_color(EQUAL), cold_dots.animate.set_color(EQUAL),
                      run_time=3.0, rate_func=smooth)
            self.play(Circumscribe(VGroup(left_therm, right_therm), color=ACCENT, buff=0.25), run_time=1.4)
            self.play(Indicate(left_num, scale_factor=1.6), Indicate(right_num, scale_factor=1.6), run_time=0.9)
            self.play(FadeIn(headline, shift=UP * 0.2), run_time=1.2, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 7.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Just like our marbles, particles in different states of matter interact in unique ways.") as tracker:
            sub = self.show_subtitle("Just like our marbles, particles in different states of matter interact in unique ways.")
            self.play(FadeOut(solid_group, cold_group, heat_arrow, q_label, headline, left_num, right_num, shift=DOWN * 0.6, lag_ratio=0.1), run_time=1.2, rate_func=rush_into)
            self.play(VGroup(left_therm, left_col, right_therm, right_col).animate.scale(0.55).to_corner(UR, buff=0.5).set_opacity(0.7), run_time=1.0, rate_func=smooth)
            self.play(FadeIn(soft_ground), FadeIn(final_marbles, shift=UP * 0.3), run_time=1.5, rate_func=smooth)
            self.play(final_marbles.animate.shift(UP * 0.12), run_time=0.7, rate_func=smooth)
            self.play(final_marbles.animate.shift(DOWN * 0.12), run_time=0.7, rate_func=smooth)
            self.play(FadeIn(final_line, shift=UP * 0.3), run_time=1.5, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 7.0))
            self.play(FadeOut(sub), run_time=0.4)

        self.play(FadeOut(final_marbles, soft_ground, final_line, left_therm, right_therm, left_col, right_col, title, shift=DOWN * 0.4), run_time=2.0, rate_func=rush_into)