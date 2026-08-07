from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.azure import AzureService
import numpy as np

import base64 as _b64_svg, os as _os

_SVG_DATA = {
    "thermometer": "PHN2ZyB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8Y2lyY2xlIGN4PSI1MCIgY3k9IjgwIiByPSIxMCIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyLjUiLz4KICA8cGF0aCBkPSJNIDQ0IDcwIEwgNDQgMjAgUSA0NCAxNSA1MCAxNSBRIDU2IDE1IDU2IDIwIEwgNTYgNzAiIHN0cm9rZT0id2hpdGUiIGZpbGw9Im5vbmUiIHN0cm9rZS13aWR0aD0iMi41Ii8+CiAgPGxpbmUgeDE9IjQ0IiB5MT0iNzAiIHgyPSI1NiIgeTI9IjcwIiBzdHJva2U9IndoaXRlIiBmaWxsPSJub25lIiBzdHJva2Utd2lkdGg9IjIuNSIvPgogIDxsaW5lIHgxPSI0NiIgeTE9IjQ1IiB4Mj0iNTQiIHkyPSI0NSIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyLjUiLz4KICA8bGluZSB4MT0iNDYiIHkxPSIzNSIgeDI9IjUyIiB5Mj0iMzUiIHN0cm9rZT0id2hpdGUiIGZpbGw9Im5vbmUiIHN0cm9rZS13aWR0aD0iMiIvPgogIDxsaW5lIHgxPSI0NiIgeTE9IjU1IiB4Mj0iNTIiIHkyPSI1NSIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyIi8+Cjwvc3ZnPg==",
    "human_figure": "PHN2ZyB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiBzdHJva2U9IndoaXRlIiBmaWxsPSJub25lIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCI+CiAgPCEtLSBIZWFkIC0tPgogIDxjaXJjbGUgY3g9IjUwIiBjeT0iMjAiIHI9IjgiLz4KICA8IS0tIEJvZHkgLS0+CiAgPGxpbmUgeDE9IjUwIiB5MT0iMjgiIHgyPSI1MCIgeTI9IjYyIi8+CiAgPCEtLSBMZWZ0IGFybSAtLT4KICA8bGluZSB4MT0iNTAiIHkxPSIzOCIgeDI9IjMwIiB5Mj0iNTIiLz4KICA8IS0tIFJpZ2h0IGFybSAtLT4KICA8bGluZSB4MT0iNTAiIHkxPSIzOCIgeDI9IjcwIiB5Mj0iNTIiLz4KICA8IS0tIExlZnQgbGVnIC0tPgogIDxsaW5lIHgxPSI1MCIgeTE9IjYyIiB4Mj0iMzMiIHkyPSI4MiIvPgogIDwhLS0gUmlnaHQgbGVnIC0tPgogIDxsaW5lIHgxPSI1MCIgeTE9IjYyIiB4Mj0iNjciIHkyPSI4MiIvPgo8L3N2Zz4="
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


class ConductionHeatTravels(VoiceoverScene):
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

        # ══════════════════════ SETUP BLOCK ══════════════════════
        def Wiggle(mobject, scale_value=1.1, **kwargs):
            # Substitute for Manim's Wiggle animation: a scale-and-rotate indicate effect.
            return Indicate(mobject, scale_factor=scale_value, **kwargs)
        # ═══════════════════════════════════════════════════════

        self.camera.background_color = ManimColor("#0D1117")

        # ══════════════════════ SETUP BLOCK ══════════════════════
        background = Rectangle(width=14.2, height=8, fill_color=ManimColor("#0D1117"),
                                fill_opacity=1, stroke_width=0).set_z_index(-10)

        title = Text("Heat Conduction", font_size=36, color=WHITE).to_edge(UP)

        candle_body = Rectangle(width=0.5, height=1.2, fill_color=ManimColor("#E0E0E0"),
                                 fill_opacity=1, stroke_color=WHITE).move_to(np.array([-5.0, -1.3, 0]))
        candle_wick = Rectangle(width=0.08, height=0.2, fill_color=BLACK, fill_opacity=1) \
            .next_to(candle_body, UP, buff=0)
        candle_group = VGroup(candle_body, candle_wick)

        flame_group = VGroup(
            Triangle(fill_color=ManimColor("#FF6D00"), fill_opacity=1, stroke_width=0)
            .scale(0.18).next_to(candle_wick, UP, buff=0.02)
        )

        foil_strip = Rectangle(width=7.0, height=0.4, fill_color=ManimColor("#B0BEC5"),
                                fill_opacity=1, stroke_color=WHITE) \
            .move_to(np.array([-1.3, -0.6, 0]))
        foil_label = Text("Aluminum Foil", font_size=22, color=WHITE) \
            .next_to(foil_strip, UP, buff=0.15)

        waves = VGroup(*[
            Arc(radius=0.18, start_angle=0, angle=PI, color=ManimColor("#FFAB40"))
            .move_to(np.array([-5.0 + 0.25 * i, -0.4 + 0.1 * i, 0]))
            for i in range(3)
        ])

        heat_path = Line(np.array([-4.7, -0.6, 0]), np.array([2.2, -0.6, 0]))
        glow_pulse = Dot(color=ManimColor("#FF8A65"), radius=0.12).move_to(heat_path.get_start())

        heat_caption = Text("Heat travels through the foil", font_size=24, color=ManimColor("#FF8A65")) \
            .next_to(foil_strip, DOWN, buff=0.9)

        butter = RoundedRectangle(corner_radius=0.1, width=0.7, height=0.4,
                                   fill_color=ManimColor("#FFD54F"), fill_opacity=1, stroke_width=0) \
            .move_to(np.array([2.4, -0.35, 0]))
        butter_label = Text("Butter", font_size=22, color=WHITE).next_to(butter, UP, buff=0.15)
        melt_shape = Ellipse(width=1.1, height=0.2, fill_color=ManimColor("#FFCA28"),
                              fill_opacity=1, stroke_width=0).move_to(butter.get_center() + DOWN * 0.15)

        therm_hot_grp = get_svg("thermometer", height=1.0).set_color(ManimColor("#FF1744")) \
            .move_to(np.array([-4.7, 1.6, 0]))
        therm_cold_grp = get_svg("thermometer", height=1.0).set_color(ManimColor("#40C4FF")) \
            .move_to(np.array([2.4, 1.6, 0]))

        mercury_hot = Rectangle(width=0.12, height=0.5, fill_color=ManimColor("#FF1744"),
                                 fill_opacity=1, stroke_width=0) \
            .move_to(therm_hot_grp.get_center() + DOWN * 0.1)
        mercury_cold = Rectangle(width=0.12, height=0.3, fill_color=ManimColor("#40C4FF"),
                                  fill_opacity=1, stroke_width=0) \
            .move_to(therm_cold_grp.get_center() + DOWN * 0.1)

        temp_hot = DecimalNumber(37, num_decimal_places=0, color=ManimColor("#FF1744")) \
            .next_to(therm_hot_grp, UP, buff=0.2)
        temp_cold = DecimalNumber(24, num_decimal_places=0, color=ManimColor("#40C4FF")) \
            .next_to(therm_cold_grp, UP, buff=0.2)

        energy_arrows = VGroup(*[
            Arrow(start=np.array([-4.0 + 2.0 * i, -0.6, 0]), end=np.array([-2.5 + 2.0 * i, -0.6, 0]),
                  color=ManimColor("#FF8A65"), buff=0)
            for i in range(3)
        ])

        vib_dots = VGroup(*[
            Dot(radius=0.06, color=ManimColor("#FFEE58")).move_to(np.array([-4.5 + 0.6 * i, -0.6, 0]))
            for i in range(10)
        ])

        label_ke = Text("vibrating atoms  →  energy passed along", font_size=28,
                         color=ManimColor("#FFCC80")).move_to(np.array([0.6, -2.15, 0]))

        readout = Text("Temperature rising in butter", font_size=24, color=ManimColor("#FFAB00")) \
            .move_to(np.array([0.6, 1.6, 0]))

        drip = Dot(color=ManimColor("#FFD54F"), radius=0.08).move_to(butter.get_bottom())
        drip_path = Line(butter.get_bottom(), butter.get_bottom() + DOWN * 0.8)

        verdict = Text("Heat flows from warm → cool", font_size=26, color=WHITE) \
            .move_to(np.array([0.6, -2.6, 0]))

        person_a = get_svg("human_figure", height=1.1).move_to(np.array([-4.0, -1.0, 0]))
        person_b = get_svg("human_figure", height=1.1).move_to(np.array([-1.5, -1.0, 0]))
        person_c = get_svg("human_figure", height=1.1).move_to(np.array([1.0, -1.0, 0]))
        person_d = get_svg("human_figure", height=1.1).move_to(np.array([3.5, -1.0, 0]))
        people = VGroup(person_a, person_b, person_c, person_d)

        analogy_text = Text("Heat transfer is like passing a ball of energy!",
                             font_size=26, color=WHITE).move_to(np.array([0.6, 1.5, 0]))
        ball = Dot(color=ManimColor("#FF6D00"), radius=0.15).move_to(person_a.get_center() + UP * 0.6)

        pass_arc_1 = ArcBetweenPoints(person_a.get_center() + UP * 0.6, person_b.get_center() + UP * 0.6, angle=-PI / 3)
        pass_arc_2 = ArcBetweenPoints(person_b.get_center() + UP * 0.6, person_c.get_center() + UP * 0.6, angle=-PI / 3)
        pass_arc_3 = ArcBetweenPoints(person_c.get_center() + UP * 0.6, person_d.get_center() + UP * 0.6, angle=-PI / 3)

        self.add(background)
        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Imagine lighting a candle under one side of a strip of aluminum foil. What happens next?") as tracker:
            sub = self.show_subtitle("Imagine lighting a candle under one side of a strip of aluminum foil. What happens next?")
            self.play(FadeIn(title, shift=UP * 0.3), rate_func=smooth, run_time=1.0)
            self.play(DrawBorderThenFill(candle_group), rate_func=smooth, run_time=1.4)
            self.play(FadeIn(flame_group, shift=UP * 0.4), rate_func=rush_from, run_time=1.0)
            self.play(Create(foil_strip), rate_func=linear, run_time=1.8)
            self.play(FadeIn(foil_label, shift=DOWN * 0.25), rate_func=smooth, run_time=0.8)
            self.wait(max(0.1, tracker.duration - 6.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="The heat from the candle warms up the foil.") as tracker:
            sub = self.show_subtitle("The heat from the candle warms up the foil.")
            self.play(AnimationGroup(*[GrowFromCenter(a) for a in waves], lag_ratio=0.25),
                      rate_func=smooth, run_time=1.4)
            self.play(MoveAlongPath(glow_pulse, heat_path),
                      foil_strip.animate.set_color(ManimColor("#FF8A65")),
                      rate_func=smooth, run_time=2.0)
            self.play(FadeIn(heat_caption, shift=UP * 0.2), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 4.8))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="This heat travels through the foil to the butter placed on top. The butter starts to melt.") as tracker:
            sub = self.show_subtitle("This heat travels through the foil to the butter placed on top. The butter starts to melt.")
            self.play(FadeOut(heat_caption, shift=DOWN * 0.3), FadeOut(glow_pulse),
                      FadeOut(waves, shift=RIGHT * 0.3), rate_func=rush_into, run_time=0.7)
            self.play(FadeIn(butter, shift=DOWN * 0.3), FadeIn(butter_label),
                      rate_func=smooth, run_time=0.8)
            self.play(Flash(butter.get_center(), color=ManimColor("#FF6D00"),
                             line_length=0.45, num_lines=14, flash_radius=0.75), run_time=0.7)
            self.play(Indicate(butter, scale_factor=1.25, color=ManimColor("#FFAB00")),
                      rate_func=smooth, run_time=0.6)
            self.play(Transform(butter, melt_shape), butter_label.animate.shift(DOWN * 0.55),
                      rate_func=smooth, run_time=1.8)
            self.wait(max(0.1, tracker.duration - 5.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="The melting butter shows us that the temperature is changing because heat is moving.") as tracker:
            sub = self.show_subtitle("The melting butter shows us that the temperature is changing because heat is moving.")
            self.play(FadeOut(butter_label, shift=DOWN * 0.2), rate_func=rush_into, run_time=0.5)
            self.play(AnimationGroup(FadeIn(therm_hot_grp, shift=DOWN * 0.4),
                                      FadeIn(therm_cold_grp, shift=DOWN * 0.4), lag_ratio=0.25),
                      rate_func=smooth, run_time=1.3)
            self.play(FadeIn(temp_hot), FadeIn(temp_cold), FadeIn(mercury_hot), FadeIn(mercury_cold), rate_func=smooth, run_time=0.8)
            self.play(temp_hot.animate.set_value(96).set_color(ManimColor("#FF1744")),
                      mercury_hot.animate.stretch_to_fit_height(1.4).shift(UP * 0.65),
                      rate_func=smooth, run_time=2.2)
            self.play(temp_cold.animate.set_value(41),
                      mercury_cold.animate.stretch_to_fit_height(0.5).shift(UP * 0.2),
                      rate_func=linear, run_time=1.5)
            self.wait(max(0.1, tracker.duration - 7.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Heat moves from the candle, which is warmer, to the butter, which is cooler. This is how energy moves from one place to another.") as tracker:
            sub = self.show_subtitle("Heat moves from the candle, which is warmer, to the butter, which is cooler. This is how energy moves from one place to another.")
            self.play(AnimationGroup(*[GrowArrow(a) for a in energy_arrows], lag_ratio=0.25),
                      rate_func=smooth, run_time=2.4)
            self.play(FadeIn(vib_dots), rate_func=smooth, run_time=0.6)
            self.play(AnimationGroup(*[Wiggle(d, scale_value=1.6) for d in vib_dots], lag_ratio=0.25),
                      rate_func=smooth, run_time=1.8)
            self.play(FadeIn(label_ke, shift=UP * 0.2), rate_func=smooth, run_time=1.0)
            self.play(energy_arrows.animate.shift(RIGHT * 0.5), vib_dots.animate.shift(RIGHT * 0.5),
                      butter.animate.shift(RIGHT * 0.5), rate_func=smooth, run_time=1.3)
            self.play(energy_arrows.animate.shift(LEFT * 0.5), vib_dots.animate.shift(LEFT * 0.5),
                      butter.animate.shift(LEFT * 0.5), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 8.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Heat transfer causes temperature changes by moving energy from warmer to cooler areas. In our cup system, heat moves into the system, causing temperature changes.") as tracker:
            sub = self.show_subtitle("Heat transfer causes temperature changes by moving energy from warmer to cooler areas. Heat moves into the system, causing temperature changes.")
            self.play(FadeOut(label_ke, shift=DOWN * 0.3), FadeOut(energy_arrows, shift=RIGHT * 0.3),
                      rate_func=rush_into, run_time=0.7)
            self.play(Circumscribe(butter, color=ManimColor("#FF6D00"), buff=0.25),
                      rate_func=smooth, run_time=1.2)
            self.play(butter.animate.set_color(ManimColor("#FFE082")),
                      Flash(butter.get_center(), color=WHITE), rate_func=smooth, run_time=0.8)
            self.play(FadeIn(readout, shift=UP * 0.2), rate_func=smooth, run_time=0.7)
            self.play(Indicate(readout, color=ManimColor("#FF1744"), scale_factor=1.35),
                      rate_func=smooth, run_time=0.8)
            self.play(FadeIn(drip), MoveAlongPath(drip, drip_path), rate_func=rush_from, run_time=0.9)
            self.play(FadeOut(drip), FadeIn(verdict, shift=UP * 0.2), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 7.2))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Think of heat transfer like passing a ball. Energy moves from a warmer object to a cooler one until everything is the same temperature. This is called thermal equilibrium. Remember, it's heat moving out, not cold moving in!") as tracker:
            sub = self.show_subtitle("Think of heat transfer like passing a ball. Energy moves from a warmer object to a cooler one until everything is the same temperature — thermal equilibrium.")
            self.play(FadeOut(VGroup(therm_hot_grp, therm_cold_grp, temp_hot, temp_cold,
                                      readout, verdict, vib_dots, mercury_hot, mercury_cold), shift=LEFT * 0.5),
                      rate_func=rush_into, run_time=1.0)
            self.play(FadeOut(VGroup(foil_strip, foil_label, butter, candle_group, flame_group),
                               shift=LEFT * 0.5), FadeOut(title, shift=UP * 0.3),
                      rate_func=rush_into, run_time=0.8)
            self.play(AnimationGroup(*[FadeIn(p, shift=UP * 0.3) for p in people], lag_ratio=0.25),
                      rate_func=smooth, run_time=1.5)
            self.play(FadeIn(analogy_text, shift=UP * 0.2), FadeIn(ball),
                      rate_func=smooth, run_time=1.0)
            self.play(MoveAlongPath(ball, pass_arc_1),
                      Indicate(person_b, scale_factor=1.15, color=ManimColor("#FF8A65")),
                      rate_func=smooth, run_time=1.0)
            self.play(MoveAlongPath(ball, pass_arc_2),
                      Indicate(person_c, scale_factor=1.15, color=ManimColor("#FF8A65")),
                      rate_func=smooth, run_time=1.0)
            self.play(MoveAlongPath(ball, pass_arc_3),
                      Indicate(person_d, scale_factor=1.15, color=ManimColor("#FF8A65")),
                      rate_func=smooth, run_time=1.0)
            self.play(FadeOut(ball, shift=RIGHT * 0.3), FadeOut(people, shift=DOWN * 0.3),
                      rate_func=rush_into, run_time=1.0)
            self.play(analogy_text.animate.move_to(ORIGIN).scale(1.15),
                      rate_func=smooth, run_time=1.2)
            self.wait(max(0.1, tracker.duration - 10.5))
            self.play(FadeOut(sub), run_time=0.4)

        self.play(FadeOut(analogy_text, shift=UP * 0.3), rate_func=rush_into, run_time=1.2)