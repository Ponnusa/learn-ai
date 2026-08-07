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




class TemperatureVsTotalEnergy(VoiceoverScene):
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

        # ═══ SETUP BLOCK: define all objects BEFORE first voiceover block ═══
        def make_dot(pos, vel, color=WHITE):
            d = Dot(point=np.array(pos, dtype=float), radius=0.06, color=color)
            d.vel = np.array(vel, dtype=float)
            return d

        chamber = RoundedRectangle(width=6, height=4, corner_radius=0.3, color=BLUE_B).move_to(ORIGIN)

        dot_specs = [
            ([-2, 1, 0], [0.6, 0.3, 0]),
            ([-1, -1, 0], [0.4, -0.5, 0]),
            ([0.5, 1.2, 0], [-0.3, 0.4, 0]),
            ([1.5, -0.8, 0], [-0.5, 0.3, 0]),
            ([-1.8, -1.2, 0], [0.5, 0.4, 0]),
            ([2, 0.5, 0], [-0.4, -0.3, 0]),
            ([0, -1.5, 0], [0.3, 0.5, 0]),
            ([-0.5, 0.3, 0], [0.4, -0.4, 0]),
        ]
        dots = [make_dot(p, v, color=WHITE) for p, v in dot_specs]

        title = Text("Gas Particles", font_size=32).to_edge(UP)

        vel_arrows = VGroup(*[
            Arrow(d.get_center(), d.get_center() + d.vel * 0.4, buff=0, color=YELLOW, stroke_width=3)
            for d in dots
        ])

        contact_point = np.array([0.3, 0.0, 0.0])
        imp_left = Arrow(contact_point, contact_point + LEFT * 0.6, buff=0, color=RED)
        imp_right = Arrow(contact_point, contact_point + RIGHT * 0.6, buff=0, color=RED)

        collision_caption = Text("Energy transferred on collision", font_size=24).to_edge(DOWN, buff=1.0)

        thermo_svg = get_svg("thermometer", height=1.0).move_to(np.array([-3.5, 0.5, 0]))
        temp_label = MathTex("T", font_size=48).next_to(thermo_svg, RIGHT, buff=0.4)
        readout = DecimalNumber(300, num_decimal_places=0, font_size=36).next_to(temp_label, RIGHT, buff=0.3)
        readout_unit = Text("K", font_size=28).next_to(readout, RIGHT, buff=0.1)
        readout_group = VGroup(readout, readout_unit)

        speed_arrows = VGroup(*[
            Arrow(d.get_center(), d.get_center() + d.vel * 0.5, buff=0, color=ORANGE, stroke_width=3)
            for d in dots
        ])

        avg_marker = Triangle(color=GREEN, fill_opacity=1).scale(0.1).next_to(chamber, DOWN, buff=0.15)

        kinetic_eq = MathTex(r"\text{KE}_{avg}", r"\propto", "T", font_size=36).to_edge(RIGHT).shift(UP * 1)

        link_arrow = Arrow(kinetic_eq.get_left(), avg_marker.get_center(), buff=0.1, color=WHITE)

        n_label = MathTex("N", font_size=40)
        n_text = Text("particles", font_size=24)
        n_group = VGroup(n_label, n_text).arrange(RIGHT, buff=0.2).to_edge(LEFT).shift(UP * 2)

        n_counter = ValueTracker(len(dots))

        new_dot_specs = [
            ([2.2, 1.3, 0], [-0.4, 0.3, 0]),
            ([-2.3, 1.4, 0], [0.3, -0.4, 0]),
            ([1.8, -1.4, 0], [-0.3, 0.4, 0]),
            ([-1.9, -0.3, 0], [0.4, 0.3, 0]),
            ([0.8, 0.1, 0], [-0.4, -0.4, 0]),
            ([-0.9, 1.6, 0], [0.3, -0.3, 0]),
            ([2.4, -0.2, 0], [-0.5, 0.2, 0]),
            ([-2.4, 0.2, 0], [0.4, 0.4, 0]),
            ([0.2, -1.7, 0], [0.2, 0.5, 0]),
        ]
        new_dots = [make_dot(p, v, color=TEAL) for p, v in new_dot_specs]
        all_dots = Group(*dots, *new_dots)

        total_eq = MathTex(r"E_{total}", "=", "N", r"\cdot \text{KE}_{avg}",
                            font_size=36).move_to(kinetic_eq.get_center())
        N_glyph = total_eq[2]

        N_link = Arrow(n_group.get_right(), total_eq.get_left(), buff=0.1, color=WHITE)

        box_T = SurroundingRectangle(temp_label, color=RED_C, buff=0.15)
        T_glyph = temp_label
        box_N = SurroundingRectangle(N_glyph, color=GREEN_C, buff=0.15)

        result_panel = RoundedRectangle(width=3, height=1.6, color=YELLOW).to_edge(RIGHT, buff=0.5).shift(DOWN * 1)
        energy_multiplier = DecimalNumber(1.00, num_decimal_places=2, font_size=40).move_to(result_panel.get_center())
        result_label = Text("x Energy", font_size=24).next_to(energy_multiplier, DOWN, buff=0.15)
        result_group = VGroup(result_panel, energy_multiplier, result_label)

        subcaption = Text("Total energy = N x average energy", font_size=24).to_edge(DOWN, buff=1.0)

        divider = Line(LEFT * 6, RIGHT * 6, color=GREY).to_edge(UP, buff=0.1)

        insight_text = Text("T = average energy per particle.\nN changes the TOTAL, not the average.",
                            font_size=28, color=WHITE, line_spacing=1.0).move_to(np.array([0.0, -2.2, 0]))
        closing_text = Text("Temperature is the average.\nEnergy is the sum.",
                            font_size=30, color=WHITE, line_spacing=1.0).move_to(np.array([0.0, -2.2, 0]))

        self.add(divider)
        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Imagine a room full of tiny, invisible balls bouncing around. These are gas particles.") as tracker:
            sub = self.show_subtitle("Imagine a room full of tiny, invisible balls bouncing around. These are gas particles.")
            self.play(DrawBorderThenFill(chamber), rate_func=smooth, run_time=2.0)
            self.play(LaggedStart(*[FadeIn(d, shift=UP * 0.35, scale=0.6) for d in dots],
                                  lag_ratio=0.25), rate_func=smooth, run_time=2.4)
            self.play(FadeIn(title, shift=DOWN * 0.3), rate_func=smooth, run_time=1.2)
            self.wait(max(0.1, tracker.duration - 0.9))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="They move in all directions, bumping into each other like kids on skateboards.") as tracker:
            sub = self.show_subtitle("They move in all directions, bumping into each other like kids on skateboards.")
            self.play(AnimationGroup(*[GrowArrow(a) for a in vel_arrows], lag_ratio=0.25),
                      rate_func=smooth, run_time=2.0)
            self.play(FadeOut(vel_arrows, shift=UP * 0.2), rate_func=rush_into, run_time=0.8)
            self.play(*[d.animate.shift(d.vel * 0.35) for d in dots], rate_func=linear, run_time=1.6)
            self.play(*[d.animate.shift(np.array([-d.vel[0], d.vel[1], 0]) * 0.3) for d in dots],
                      rate_func=linear, run_time=1.4)
            self.wait(max(0.1, tracker.duration - 0.9))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="When they collide, they swap energy. One might slow down, another speeds up.") as tracker:
            sub = self.show_subtitle("When they collide, they swap energy. One might slow down, another speeds up.")
            self.play(dots[0].animate.move_to(contact_point + LEFT * 0.13),
                      dots[1].animate.move_to(contact_point + RIGHT * 0.13),
                      rate_func=linear, run_time=1.6)
            self.play(Flash(contact_point, color=WHITE, line_length=0.35, num_lines=14,
                            flash_radius=0.5), run_time=0.7)
            self.play(GrowArrow(imp_left), GrowArrow(imp_right), rate_func=smooth, run_time=1.0)
            self.play(dots[0].animate.shift(np.array([-1.6, -0.5, 0])),
                      imp_left.animate.shift(np.array([-1.6, -0.5, 0])),
                      dots[1].animate.shift(np.array([1.6, 0.5, 0])),
                      imp_right.animate.shift(np.array([1.6, 0.5, 0])),
                      rate_func=smooth, run_time=1.6)
            self.play(FadeOut(imp_left, imp_right, shift=UP * 0.2), rate_func=rush_into, run_time=0.6)
            self.play(FadeIn(collision_caption, shift=UP * 0.2), rate_func=smooth, run_time=1.2)
            self.wait(max(0.1, tracker.duration - 0.9))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="But what does this have to do with temperature?") as tracker:
            sub = self.show_subtitle("But what does this have to do with temperature?")
            self.play(FadeOut(collision_caption, shift=DOWN * 0.3), rate_func=rush_into, run_time=0.8)
            self.play(FadeIn(thermo_svg, shift=LEFT * 0.5, scale=0.9), rate_func=smooth, run_time=1.6)
            self.play(FadeIn(temp_label, shift=RIGHT * 0.2), rate_func=smooth, run_time=1.0)
            self.play(FadeIn(readout_group, shift=UP * 0.25), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 0.9))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Temperature is like the average speed of all these particles. Even if some go faster and others slower, the average can stay the same.") as tracker:
            sub = self.show_subtitle("Temperature is like the average speed of all these particles. Even if some go faster and others slower, the average can stay the same.")
            self.play(FadeOut(title, shift=UP * 0.3), rate_func=rush_into, run_time=0.7)
            self.play(AnimationGroup(*[GrowArrow(a) for a in speed_arrows], lag_ratio=0.2),
                      rate_func=smooth, run_time=2.4)
            self.play(FadeIn(avg_marker, shift=UP * 0.15), rate_func=smooth, run_time=1.0)
            self.play(Write(kinetic_eq), rate_func=smooth, run_time=1.8)
            self.play(GrowArrow(link_arrow), rate_func=smooth, run_time=1.2)
            self.wait(max(0.1, tracker.duration - 0.9))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Now, if more particles join the fun, the total energy in the room goes up.") as tracker:
            sub = self.show_subtitle("Now, if more particles join the fun, the total energy in the room goes up.")
            self.play(FadeOut(speed_arrows, shift=UP * 0.2), FadeOut(link_arrow, shift=DOWN * 0.2),
                      FadeOut(avg_marker, shift=DOWN * 0.2), rate_func=rush_into, run_time=0.8)
            self.play(FadeIn(n_group, shift=DOWN * 0.2), rate_func=smooth, run_time=0.8)
            self.play(LaggedStart(*[FadeIn(d, scale=0.4, shift=UP * 0.2) for d in new_dots],
                                  lag_ratio=0.2),
                      n_counter.animate.set_value(18), rate_func=smooth, run_time=3.0)
            self.play(Indicate(readout, scale_factor=1.15, color=RED_C), run_time=1.0)
            self.wait(max(0.1, tracker.duration - 0.9))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="But the average speed, or temperature, might not change if they all move similarly.") as tracker:
            sub = self.show_subtitle("But the average speed, or temperature, might not change if they all move similarly.")
            self.play(*[d.animate.shift(d.vel * 0.25) for d in all_dots], rate_func=linear, run_time=1.4)
            self.play(TransformMatchingTex(kinetic_eq, total_eq), rate_func=smooth, run_time=1.6)
            self.play(GrowArrow(N_link), rate_func=smooth, run_time=1.2)
            self.play(AnimationGroup(FadeIn(subcaption, shift=UP * 0.2),
                                     Indicate(N_glyph, scale_factor=1.4, color=GREEN_C),
                                     lag_ratio=0.25), rate_func=smooth, run_time=2.2)
            self.wait(max(0.1, tracker.duration - 0.9))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So, temperature tells us about the average speed, not the total energy.") as tracker:
            sub = self.show_subtitle("So, temperature tells us about the average speed, not the total energy.")
            self.play(FadeOut(subcaption, shift=DOWN * 0.3), rate_func=rush_into, run_time=0.6)
            self.play(Create(box_T), rate_func=smooth, run_time=1.2)
            self.wait(0.5)
            self.play(Indicate(T_glyph, scale_factor=1.8, color=RED_C), run_time=1.2)
            self.play(Create(box_N), rate_func=smooth, run_time=1.0)
            self.play(Indicate(N_glyph, scale_factor=1.8, color=GREEN_C), run_time=1.2)
            self.play(FadeIn(insight_text, shift=UP * 0.2), rate_func=smooth, run_time=1.6)
            self.wait(max(0.1, tracker.duration - 0.9))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Next time you feel the warmth of the sun, remember it's those tiny particles moving faster!") as tracker:
            sub = self.show_subtitle("Next time you feel the warmth of the sun, remember it's those tiny particles moving faster!")
            self.play(FadeOut(insight_text, shift=DOWN * 0.3), rate_func=rush_into, run_time=0.7)
            self.play(FadeIn(result_group, shift=DOWN * 0.2), rate_func=smooth, run_time=1.2)
            self.play(energy_multiplier.animate.set_value(3.00),
                      *[d.animate.shift(d.vel * 0.2) for d in all_dots],
                      rate_func=smooth, run_time=2.2)
            self.play(Circumscribe(result_panel, color=YELLOW, buff=0.25), run_time=1.5)
            self.play(Flash(energy_multiplier.get_center(), color=YELLOW, num_lines=16), run_time=0.8)
            self.play(Indicate(readout, scale_factor=1.3, color=RED_C), run_time=1.0)
            self.wait(max(0.1, tracker.duration - 0.9))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Temperature is the average. Energy is the sum.") as tracker:
            sub = self.show_subtitle("Temperature is the average. Energy is the sum.")
            self.play(FadeOut(N_link, shift=DOWN * 0.3), FadeOut(box_T, shift=DOWN * 0.3),
                      FadeOut(box_N, shift=DOWN * 0.3), FadeOut(result_group, shift=DOWN * 0.3),
                      FadeOut(total_eq, shift=DOWN * 0.3), FadeOut(n_group, shift=UP * 0.3),
                      FadeOut(temp_label, shift=RIGHT * 0.2),
                      rate_func=rush_into, run_time=1.4)
            self.play(FadeIn(closing_text, shift=UP * 0.25), rate_func=smooth, run_time=1.6)
            self.play(*[d.animate.shift(d.vel * 0.08) for d in all_dots], rate_func=smooth, run_time=2.0)
            self.wait(max(0.1, tracker.duration - 0.9))
            self.play(FadeOut(sub), run_time=0.4)

        self.play(FadeOut(chamber, shift=DOWN * 0.2), FadeOut(all_dots, shift=DOWN * 0.2),
                  FadeOut(thermo_svg, shift=DOWN * 0.2), FadeOut(readout_group, shift=DOWN * 0.2),
                  FadeOut(closing_text, shift=DOWN * 0.2), FadeOut(divider),
                  rate_func=smooth, run_time=1.8)