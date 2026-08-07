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


class CandyDissolveTemperature(VoiceoverScene):
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

        # ═══ SETUP BLOCK: define ALL objects before first voiceover ═══
        DYE_C = "#FF6EC7"
        HOT_C = "#FF4500"

        background = Rectangle(width=15, height=9, fill_color="#0D1117",
                                fill_opacity=1, stroke_width=0).move_to(ORIGIN)

        _s, _e = np.array([0, 3.5, 0]), np.array([0, -3.5, 0])
        if np.linalg.norm(_e - _s) > 0.01:
            divider = DashedLine(_s, _e, color=GRAY_D, stroke_width=2)
        else:
            divider = VGroup()

        title1 = Text("Same candy. Different water.", font_size=28, color=WHITE).move_to(UP * 3.2)
        title2 = Text("Hot water: color races outward", font_size=30, color=DYE_C).move_to(UP * 3.2)

        hot_center = RIGHT * 3 + DOWN * 0.5
        cold_center = LEFT * 3 + DOWN * 0.5

        hot_beaker = RoundedRectangle(width=2.4, height=2.8, corner_radius=0.15,
                                       color=GRAY_B, stroke_width=3).move_to(hot_center)
        hot_water = Rectangle(width=2.1, height=2.2, fill_color=RED, fill_opacity=0.45,
                               stroke_width=0).move_to(hot_center + DOWN * 0.2)

        cold_beaker = RoundedRectangle(width=2.4, height=2.8, corner_radius=0.15,
                                        color=GRAY_B, stroke_width=3).move_to(cold_center)
        cold_water = Rectangle(width=2.1, height=2.2, fill_color=BLUE, fill_opacity=0.45,
                                stroke_width=0).move_to(cold_center + DOWN * 0.2)

        thermometer_hot = get_svg("thermometer", height=0.9).set_color(RED).next_to(hot_beaker, RIGHT, buff=0.35)
        temp_label_80C = Text("80°C", font_size=24, color=RED).next_to(thermometer_hot, DOWN, buff=0.15)

        thermometer_cold = get_svg("thermometer", height=0.9).set_color(BLUE).next_to(cold_beaker, LEFT, buff=0.35)
        temp_label_5C = Text("5°C", font_size=24, color=BLUE).next_to(thermometer_cold, DOWN, buff=0.15)

        candy = Dot(radius=0.16, color=YELLOW).move_to(hot_center + UP * 2.2)
        candy_rest = hot_water.get_center() + UP * 0.3

        candy2 = Dot(radius=0.16, color=YELLOW).move_to(cold_center + UP * 2.2)
        candy2_rest = cold_water.get_center() + UP * 0.3

        gravity_arrow = Arrow(candy_rest + UP * 0.35, candy_rest + DOWN * 0.35, buff=0, color=BLUE_D, stroke_width=5)
        gravity_label = Text("Gravity", font_size=18, color=BLUE_D).next_to(gravity_arrow, LEFT, buff=0.15)
        normal_arrow = Arrow(candy_rest + DOWN * 0.35, candy_rest + UP * 0.35, buff=0, color=GREEN_D, stroke_width=5)
        normal_label = Text("Normal", font_size=18, color=GREEN_D).next_to(normal_arrow, RIGHT, buff=0.15)

        gravity2 = Arrow(candy2_rest + UP * 0.35, candy2_rest + DOWN * 0.35, buff=0, color=BLUE_D, stroke_width=5)
        gravity2_label = Text("Gravity", font_size=18, color=BLUE_D).next_to(gravity2, LEFT, buff=0.15)
        normal2 = Arrow(candy2_rest + DOWN * 0.35, candy2_rest + UP * 0.35, buff=0, color=GREEN_D, stroke_width=5)
        normal2_label = Text("Normal", font_size=18, color=GREEN_D).next_to(normal2, RIGHT, buff=0.15)

        dye_source = Dot(color=DYE_C, radius=0.12).move_to(hot_water.get_center())
        dye_rings = VGroup(*[
            Circle(radius=r, color=DYE_C, stroke_width=3).move_to(dye_source.get_center())
            for r in [0.35, 0.65, 0.95]
        ])
        dye_arrow_dirs = [UP, DOWN, LEFT, RIGHT]
        dye_arrows = VGroup(*[
            Arrow(dye_source.get_center(), dye_source.get_center() + d * 0.9, buff=0, color=DYE_C, stroke_width=3)
            for d in dye_arrow_dirs
        ])

        hot_offsets = [UP * 0.6 + LEFT * 0.5, UP * 0.3 + RIGHT * 0.4, DOWN * 0.2 + LEFT * 0.3,
                       DOWN * 0.5 + RIGHT * 0.5, UP * 0.1 + LEFT * 0.1, DOWN * 0.7 + RIGHT * 0.1]
        hot_dots = VGroup(*[Dot(radius=0.06, color=RED_A).move_to(hot_water.get_center() + off) for off in hot_offsets])
        hot_vel_arrows = VGroup(*[
            Arrow(dot.get_center(), dot.get_center() + RIGHT * 0.35, buff=0, color=RED_A, stroke_width=2)
            for dot in hot_dots
        ])
        hot_speed_eq = MathTex(r"v \propto \sqrt{T}", color=WHITE, font_size=34).next_to(hot_beaker, UP, buff=0.5)
        hot_hops = [
            [np.array([0.3 * np.cos(a), 0.3 * np.sin(a), 0]) for a in [0.5 + i, 2.1 + i, 4.0 + i]]
            for i in range(len(hot_dots))
        ]

        cold_offsets = [UP * 0.4 + LEFT * 0.3, DOWN * 0.3 + RIGHT * 0.3, UP * 0.1 + RIGHT * 0.5, DOWN * 0.5 + LEFT * 0.2]
        cold_dots = VGroup(*[Dot(radius=0.06, color=BLUE_A).move_to(cold_water.get_center() + off) for off in cold_offsets])
        cold_vel_arrows = VGroup(*[
            Arrow(dot.get_center(), dot.get_center() + RIGHT * 0.15, buff=0, color=BLUE_A, stroke_width=2)
            for dot in cold_dots
        ])
        cold_hops = [
            [np.array([0.12 * np.cos(a), 0.12 * np.sin(a), 0]) for a in [0.3 + i, 1.8 + i, 3.4 + i]]
            for i in range(len(cold_dots))
        ]

        insight_box = RoundedRectangle(width=6, height=1.4, corner_radius=0.2, color=YELLOW).move_to(DOWN * 2.0)
        insight_text = Text("Hotter -> Faster particles -> Faster dissolving",
                             font_size=22, color=WHITE).move_to(insight_box.get_center())
        insight_group = VGroup(insight_box, insight_text)

        hot_timer = DecimalNumber(0, num_decimal_places=0, color=WHITE).move_to(hot_center + DOWN * 2.0)
        cold_timer = DecimalNumber(0, num_decimal_places=0, color=WHITE).move_to(cold_center + DOWN * 2.0)
        ratio_eq = MathTex(r"t_{cold} \approx 8 \times t_{hot}", color=WHITE).move_to(DOWN * 2.0)

        cold_group = VGroup(cold_beaker, cold_water)
        hot_group = VGroup(hot_beaker, hot_water)
        timers_group = VGroup(hot_timer, cold_timer)

        final_line = Text("Temperature controls particle speed and dissolving rate.",
                           font_size=26, color=WHITE).move_to(ORIGIN)

        self.add(background, divider)
        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Imagine dropping a piece of candy into hot water. It dissolves quickly, right? But why does that happen?") as tracker:
            sub = self.show_subtitle("Imagine dropping a piece of candy into hot water. It dissolves quickly, right? But why does that happen?")
            self.play(FadeIn(title1, shift=UP * 0.3), rate_func=smooth, run_time=1.0)
            self.play(DrawBorderThenFill(hot_beaker), rate_func=smooth, run_time=1.6)
            self.play(FadeIn(hot_water, shift=UP * 0.4), rate_func=rush_from, run_time=1.0)
            self.play(FadeIn(thermometer_hot, shift=RIGHT * 0.5), FadeIn(temp_label_80C), rate_func=smooth, run_time=1.0)
            self.play(FadeIn(candy, shift=UP * 0.5), rate_func=smooth, run_time=0.8)
            self.play(candy.animate.move_to(candy_rest), GrowArrow(gravity_arrow), FadeIn(gravity_label), rate_func=rush_into, run_time=1.2)
            self.play(GrowArrow(normal_arrow), FadeIn(normal_label), rate_func=smooth, run_time=0.8)
            self.play(FadeOut(gravity_arrow), FadeOut(gravity_label), FadeOut(normal_arrow), FadeOut(normal_label), rate_func=rush_into, run_time=0.6)
            self.wait(max(0.1, tracker.duration - 8.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Now, think about adding food coloring to hot water. It spreads out fast. But in cold water, it takes its time. What's going on here?") as tracker:
            sub = self.show_subtitle("Now, think about adding food coloring to hot water. It spreads out fast. But in cold water, it takes its time. What's going on here?")
            self.play(ReplacementTransform(title1, title2), rate_func=smooth, run_time=1.0)
            self.play(FadeIn(dye_source, scale=0.6), rate_func=smooth, run_time=0.6)
            self.play(AnimationGroup(*[GrowFromCenter(r) for r in dye_rings], lag_ratio=0.25), rate_func=smooth, run_time=2.6)
            self.play(AnimationGroup(*[GrowArrow(a) for a in dye_arrows], lag_ratio=0.2), rate_func=smooth, run_time=1.8)
            self.play(hot_water.animate.set_fill(HOT_C, opacity=0.6), rate_func=smooth, run_time=1.2)
            self.wait(max(0.1, tracker.duration - 7.6))
            self.play(FadeOut(dye_rings, shift=UP * 0.2), FadeOut(dye_arrows), FadeOut(dye_source), FadeOut(sub), run_time=0.9)

        with self.voiceover(text="The secret lies in the tiny particles that make up the water. In hot water, these particles are like energetic dancers, moving quickly and bumping into each other.") as tracker:
            sub = self.show_subtitle("The secret lies in the tiny particles that make up the water. In hot water, these particles are like energetic dancers, moving quickly and bumping into each other.")
            self.play(FadeIn(hot_dots, scale=0.7), rate_func=smooth, run_time=1.0)
            self.play(AnimationGroup(*[GrowArrow(v) for v in hot_vel_arrows], lag_ratio=0.2), rate_func=smooth, run_time=2.0)
            self.play(FadeIn(hot_speed_eq, shift=UP * 0.2), rate_func=smooth, run_time=1.0)
            self.play(Indicate(hot_speed_eq, color=YELLOW, scale_factor=1.2), rate_func=smooth, run_time=0.8)
            for h in range(3):
                self.play(
                    *[hot_dots[i].animate.shift(hot_hops[i][h]) for i in range(len(hot_dots))],
                    *[hot_vel_arrows[i].animate.shift(hot_hops[i][h]) for i in range(len(hot_vel_arrows))],
                    rate_func=linear, run_time=0.55,
                )
            self.play(Indicate(thermometer_hot, color=RED, scale_factor=1.15), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 7.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="In cold water, the particles are more like slow walkers, moving gently and not as often.") as tracker:
            sub = self.show_subtitle("In cold water, the particles are more like slow walkers, moving gently and not as often.")
            self.play(DrawBorderThenFill(cold_beaker), rate_func=smooth, run_time=1.4)
            self.play(FadeIn(cold_water, shift=UP * 0.3), FadeIn(thermometer_cold, shift=LEFT * 0.5), FadeIn(temp_label_5C), rate_func=smooth, run_time=1.1)
            self.play(FadeIn(candy2, shift=UP * 0.5), rate_func=smooth, run_time=0.7)
            self.play(candy2.animate.move_to(candy2_rest), GrowArrow(gravity2), FadeIn(gravity2_label), rate_func=rush_into, run_time=1.1)
            self.play(GrowArrow(normal2), FadeIn(normal2_label), rate_func=smooth, run_time=0.7)
            self.play(FadeOut(gravity2), FadeOut(gravity2_label), FadeOut(normal2), FadeOut(normal2_label), rate_func=rush_into, run_time=0.5)
            self.play(FadeIn(cold_dots, scale=0.7), AnimationGroup(*[GrowArrow(v) for v in cold_vel_arrows], lag_ratio=0.2), rate_func=smooth, run_time=2.0)
            for h in range(2):
                self.play(
                    *[cold_dots[i].animate.shift(cold_hops[i][h]) for i in range(len(cold_dots))],
                    *[cold_vel_arrows[i].animate.shift(cold_hops[i][h]) for i in range(len(cold_vel_arrows))],
                    *[hot_dots[i].animate.shift(hot_hops[i][h + 1]) for i in range(len(hot_dots))],
                    *[hot_vel_arrows[i].animate.shift(hot_hops[i][h + 1]) for i in range(len(hot_vel_arrows))],
                    rate_func=smooth, run_time=1.0,
                )
            self.play(candy.animate.scale(0.35), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 10.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So, the hotter the water, the faster the particles move. And the faster they move, the quicker they can spread things like candy or color.") as tracker:
            sub = self.show_subtitle("So, the hotter the water, the faster the particles move. And the faster they move, the quicker they can spread things like candy or color.")
            self.play(FadeOut(title2, shift=UP * 0.3), FadeOut(hot_speed_eq, shift=UP * 0.2), rate_func=rush_into, run_time=0.8)
            self.play(hot_water.animate.set_opacity(0.2), cold_water.animate.set_opacity(0.2), rate_func=smooth, run_time=0.8)
            self.play(FadeIn(insight_group, shift=DOWN * 0.2), rate_func=smooth, run_time=1.2)
            self.play(Circumscribe(insight_box, color=YELLOW, buff=0.15), rate_func=smooth, run_time=1.8)
            self.play(Indicate(hot_vel_arrows, color=YELLOW, scale_factor=1.4), rate_func=smooth, run_time=1.2)
            self.play(Indicate(thermometer_hot, color=RED, scale_factor=1.2), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 7.2))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="That's why temperature is so important. It changes how fast particles move in a liquid.") as tracker:
            sub = self.show_subtitle("That's why temperature is so important. It changes how fast particles move in a liquid.")
            self.play(FadeOut(insight_group, shift=UP * 0.3), FadeOut(hot_vel_arrows), FadeOut(cold_vel_arrows), rate_func=rush_into, run_time=0.8)
            self.play(FadeIn(hot_timer), FadeIn(cold_timer), rate_func=smooth, run_time=0.7)
            self.play(hot_timer.animate.set_value(12).set_color(GREEN), FadeOut(candy, scale=0.2),
                      hot_water.animate.set_fill(DYE_C, opacity=0.75), rate_func=smooth, run_time=1.4)
            self.play(cold_timer.animate.set_value(95).set_color(BLUE), candy2.animate.scale(0.85),
                      cold_water.animate.set_opacity(0.25), rate_func=linear, run_time=2.2)
            self.play(Circumscribe(hot_timer, color=GREEN), rate_func=smooth, run_time=1.2)
            self.play(FadeIn(ratio_eq, shift=UP * 0.2), rate_func=smooth, run_time=1.0)
            self.play(Flash(ratio_eq, color=YELLOW, flash_radius=1.2), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 8.3))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Next time you see something dissolve or spread in water, remember: it's all about those dancing particles and their energy!") as tracker:
            sub = self.show_subtitle("Next time you see something dissolve or spread in water, remember: it's all about those dancing particles and their energy!")
            self.play(FadeOut(cold_group, shift=DOWN * 0.3), FadeOut(thermometer_cold, shift=DOWN * 0.3),
                      FadeOut(temp_label_5C), FadeOut(candy2), FadeOut(cold_dots), FadeOut(hot_dots),
                      FadeOut(timers_group), FadeOut(ratio_eq, shift=UP * 0.3), FadeOut(divider),
                      rate_func=rush_into, run_time=1.3)
            self.play(hot_group.animate.move_to(LEFT * 3.4 + DOWN * 0.3),
                      thermometer_hot.animate.move_to(LEFT * 5.6 + DOWN * 0.3),
                      temp_label_80C.animate.move_to(LEFT * 5.6 + DOWN * 1.9),
                      rate_func=smooth, run_time=1.4)
            self.play(hot_water.animate.shift(UP * 0.06), rate_func=there_and_back, run_time=1.0)
            self.play(FadeIn(final_line, shift=UP * 0.3), rate_func=smooth, run_time=1.4)
            self.play(Circumscribe(final_line, color=YELLOW, fade_out=True), rate_func=smooth, run_time=1.2)
            self.wait(max(0.1, tracker.duration - 6.5))
            self.play(FadeOut(sub), FadeOut(final_line), FadeOut(hot_group), FadeOut(thermometer_hot),
                      FadeOut(temp_label_80C), rate_func=rush_into, run_time=1.2)