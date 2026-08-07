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




class InsulatedCupScene(VoiceoverScene):
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
        self.camera.background_color = ManimColor("#0B1120")

        # ═══ SETUP BLOCK: define all objects used below ═══
        C_GOLD = ManimColor("#FFD700")

        background = Rectangle(width=14.5, height=8.2, fill_color=ManimColor("#0B1120"),
                                fill_opacity=1, stroke_width=0)

        question = Text("How can a cup use less material?", font_size=32, color=WHITE).move_to(UP * 2.6)
        hook_math = MathTex(r"\text{Material} \downarrow \quad \text{Performance} \uparrow",
                             font_size=34, color=C_GOLD).next_to(question, DOWN, buff=0.4)

        cup_start_b7 = np.array([-3.0, -1.0, 0])
        cup_body = Polygon(
            np.array([-0.6, -1.0, 0]), np.array([0.6, -1.0, 0]),
            np.array([0.8, 1.0, 0]), np.array([-0.8, 1.0, 0]),
            color=WHITE, fill_color=ManimColor("#4A5568"), fill_opacity=0.8
        )
        cup_rim = Ellipse(width=1.6, height=0.25, color=WHITE).move_to(cup_body.get_top())
        cup_handle = Arc(radius=0.4, start_angle=-PI / 2, angle=PI, color=WHITE).next_to(cup_body, RIGHT, buff=-0.1)
        cup = VGroup(cup_body, cup_rim, cup_handle).scale(0.9).move_to(np.array([3.5, -1, 0]))

        bulb_glass = Circle(radius=0.5, color=WHITE).move_to(np.array([3.2, 1.5, 0]))
        bulb_base = Rectangle(width=0.3, height=0.3, color=GRAY, fill_opacity=1).next_to(bulb_glass, DOWN, buff=0)
        bulb_filament = Line(bulb_glass.get_top() + DOWN * 0.1, bulb_glass.get_bottom() + UP * 0.1, color=YELLOW)
        bulb = VGroup(bulb_glass, bulb_base, bulb_filament)
        bulb_rays = VGroup(*[
            Line(bulb_glass.get_center(),
                 bulb_glass.get_center() + np.array([np.cos(a), np.sin(a), 0]) * 0.9, color=YELLOW)
            for a in np.linspace(0, 2 * PI, 8, endpoint=False)
        ])

        mirrors = Rectangle(width=0.2, height=2.0, color=C_GOLD, fill_color=C_GOLD,
                             fill_opacity=0.6).move_to(np.array([0.5, 0, 0]))

        in_rays = VGroup(*[
            Arrow(bulb_glass.get_center() + LEFT * 2 + UP * 0.3 * i, bulb_glass.get_center() + UP * 0.3 * i,
                  color=YELLOW, buff=0) for i in range(-1, 2)
        ])
        reflected_rays = VGroup(*[
            Arrow(mirrors.get_center() + UP * 0.3 * i, mirrors.get_center() + RIGHT * 2 + UP * 0.3 * i,
                  color=C_GOLD, buff=0) for i in range(-1, 2)
        ])
        radiation_label = Text("Radiation", font_size=24, color=WHITE).next_to(mirrors, UP, buff=0.5)

        shell_outer = Circle(radius=1.4, color=WHITE).move_to(ORIGIN)
        shell_gap = Circle(radius=1.1, color=GRAY, stroke_opacity=0.5).move_to(ORIGIN)
        shell_inner = Circle(radius=0.8, color=WHITE).move_to(ORIGIN)
        shells = VGroup(shell_outer, shell_gap, shell_inner)
        legend = VGroup(
            Text("Outer wall", font_size=20).move_to(np.array([3, 1.5, 0])),
            Text("Vacuum gap", font_size=20).move_to(np.array([3, 1.0, 0])),
            Text("Inner wall", font_size=20).move_to(np.array([3, 0.5, 0])),
        )

        gap_arrow_L = Arrow(LEFT * 0.3, LEFT * 1.8, color=BLUE, buff=0)
        gap_arrow_R = Arrow(RIGHT * 0.3, RIGHT * 1.8, color=BLUE, buff=0)
        vacuum_text = Text("Vacuum gap blocks conduction", font_size=22, color=WHITE).move_to(DOWN * 1.6)
        conduction_path = Arrow(LEFT * 2.1, RIGHT * 2.1, color=RED, buff=0)
        conduction_cross = Cross(scale_factor=0.4, color=RED).move_to(ORIGIN)

        bench = Rectangle(width=6, height=0.2, color=WHITE, fill_opacity=1, fill_color=GRAY).move_to(DOWN * 2)
        weight_arrow = Arrow(cup_start_b7, cup_start_b7 + DOWN * 1.0, color=RED, buff=0)
        normal_arrow = Arrow(cup_start_b7, cup_start_b7 + UP * 1.0, color=BLUE, buff=0)
        bench_right_seat = np.array([2.5, -1.8, 0])
        bench_delta = bench_right_seat - cup_start_b7

        plain_cup = VGroup(
            Polygon(np.array([-0.6, -1.0, 0]), np.array([0.6, -1.0, 0]),
                    np.array([0.75, 0.9, 0]), np.array([-0.75, 0.9, 0]),
                    color=WHITE, fill_color=ManimColor("#718096"), fill_opacity=0.8)
        ).move_to(np.array([-2.5, -1.0, 0]))

        label_A = Text("Plain Cup", font_size=22).move_to(np.array([-2.5, -2.3, 0]))
        label_B = Text("Insulated Cup", font_size=22).move_to(np.array([2.5, -2.3, 0]))

        therm_A = get_svg("thermometer", height=1.2).move_to(np.array([-2.5, 0.5, 0]))
        therm_B = get_svg("thermometer", height=1.2).move_to(np.array([2.5, 0.5, 0]))
        merc_A = Rectangle(width=0.15, height=0.1, color=RED, fill_color=RED,
                            fill_opacity=1).move_to(therm_A.get_bottom() + UP * 0.2)
        merc_B = Rectangle(width=0.15, height=0.1, color=RED, fill_color=RED,
                            fill_opacity=1).move_to(therm_B.get_bottom() + UP * 0.2)
        temp_A_tracker = ValueTracker(20)
        temp_B_tracker = ValueTracker(20)
        read_A = DecimalNumber(20, num_decimal_places=0, font_size=22).next_to(therm_A, RIGHT, buff=0.2)
        read_B = DecimalNumber(20, num_decimal_places=0, font_size=22).next_to(therm_B, RIGHT, buff=0.2)
        read_A.add_updater(lambda d: d.set_value(temp_A_tracker.get_value()))
        read_B.add_updater(lambda d: d.set_value(temp_B_tracker.get_value()))
        loss_arrows = VGroup(*[
            Arrow(therm_B.get_top() + UP * 0.1 * i, therm_B.get_top() + UP * (0.5 + 0.1 * i),
                  color=RED, buff=0) for i in range(3)
        ])

        bar_L = Rectangle(width=1.0, height=2.0, color=C_GOLD, fill_color=C_GOLD,
                           fill_opacity=0.7).move_to(np.array([-2, -1, 0]))
        bar_R = Rectangle(width=1.0, height=2.0, color=BLUE, fill_color=BLUE,
                           fill_opacity=0.7).move_to(np.array([2, -1, 0]))
        label_L = Text("Old Design", font_size=20).next_to(bar_L, DOWN, buff=0.2)
        label_R = Text("New Design", font_size=20).next_to(bar_R, DOWN, buff=0.2)
        count_tracker = ValueTracker(5)
        count_num = DecimalNumber(5, num_decimal_places=0, font_size=28).next_to(bar_L, UP, buff=0.2)
        count_num.add_updater(lambda d: d.set_value(count_tracker.get_value()))
        reduction_arrow = Arrow(bar_L.get_top(), bar_R.get_top(), color=WHITE, buff=0.1)

        earth_globe = Circle(radius=1.0, color=BLUE, fill_color=BLUE, fill_opacity=0.6).move_to(np.array([3.3, 0, 0]))
        cont1 = Circle(radius=0.2, color=GREEN, fill_color=GREEN,
                        fill_opacity=1).move_to(earth_globe.get_center() + np.array([0.3, 0.3, 0]))
        cont2 = Circle(radius=0.15, color=GREEN, fill_color=GREEN,
                        fill_opacity=1).move_to(earth_globe.get_center() + np.array([-0.3, -0.2, 0]))
        cont3 = Circle(radius=0.12, color=GREEN, fill_color=GREEN,
                        fill_opacity=1).move_to(earth_globe.get_center() + np.array([0.1, -0.4, 0]))
        earth = VGroup(earth_globe, cont1, cont2, cont3)
        orbit_circle = Circle(radius=1.6, color=GRAY).move_to(earth_globe.get_center())
        orbit_dot = Dot(color=WHITE).move_to(orbit_circle.point_at_angle(0))
        co2_text = Text("CO2", font_size=22, color=GRAY).next_to(orbit_circle, UP, buff=0.2)

        headline = Text("Smart Design = Less Waste", font_size=34, color=C_GOLD).move_to(UP * 1.5)
        pct_tracker = ValueTracker(0)
        pct_num = DecimalNumber(0, num_decimal_places=0, font_size=48, color=C_GOLD).move_to(DOWN * 0.2)
        pct_num.add_updater(lambda d: d.set_value(pct_tracker.get_value()))
        pct_suffix = Text("%", font_size=48, color=C_GOLD).next_to(pct_num, RIGHT, buff=0.05)

        check_circle = Circle(radius=0.6, color=GREEN).move_to(DOWN * 1.5)
        check = Text("check", font_size=32, color=GREEN).move_to(check_circle.get_center())
        final_check_math = MathTex(r"\checkmark", font_size=36, color=GREEN)
        tagline = Text("Design smart. Waste less.", font_size=28, color=WHITE).move_to(DOWN * 1)
        # ═══ END SETUP BLOCK ═══

        self.add(background)
        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Imagine you have a cup. How can you make it use less material but still work really well?") as tracker:
            sub = self.show_subtitle("Imagine you have a cup. How can you make it use less material but still work really well?")
            self.play(FadeIn(question, shift=DOWN * 0.6), run_time=1.6, rate_func=smooth)
            self.wait(0.3)
            self.play(Write(hook_math), run_time=1.4, rate_func=smooth)
            self.play(Indicate(hook_math, color=C_GOLD), run_time=0.6)
            self.wait(max(0.1, tracker.duration - 4.5))
            self.play(FadeOut(hook_math, shift=DOWN * 0.3),
                      question.animate.scale(0.64).to_edge(UP, buff=0.35),
                      run_time=1.0, rate_func=smooth)
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Let's take a closer look at this cup.") as tracker:
            sub = self.show_subtitle("Let's take a closer look at this cup.")
            self.play(cup.animate.move_to(ORIGIN), run_time=1.8, rate_func=smooth)
            self.play(Indicate(cup_rim, color=C_GOLD, scale_factor=1.1), run_time=0.8)
            self.wait(max(0.1, tracker.duration - 0.9))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Let's think about light and heat. If your cup reflects light, it stays cooler.") as tracker:
            sub = self.show_subtitle("Let's think about light and heat. If your cup reflects light, it stays cooler.")
            self.play(cup.animate.shift(LEFT * 3.2),
                      AnimationGroup(Create(bulb_glass), FadeIn(bulb_base), Write(bulb_filament), lag_ratio=0.25),
                      run_time=1.6, rate_func=smooth)
            self.play(AnimationGroup(*[GrowFromCenter(r) for r in bulb_rays], lag_ratio=0.12),
                      run_time=1.2, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 3.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Shiny materials like metals can help with that.") as tracker:
            sub = self.show_subtitle("Shiny materials like metals can help with that.")
            self.play(FadeIn(mirrors, shift=RIGHT * 0.2), run_time=1.0, rate_func=smooth)
            self.play(AnimationGroup(*[GrowArrow(a) for a in in_rays], lag_ratio=0.25),
                      run_time=1.6, rate_func=smooth)
            self.play(AnimationGroup(*[GrowArrow(a) for a in reflected_rays], lag_ratio=0.25),
                      run_time=1.6, rate_func=smooth)
            self.play(FadeIn(radiation_label, shift=UP * 0.2), run_time=0.8)
            self.wait(max(0.1, tracker.duration - 3.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Now, what about the cup's layers? If they don't touch much, less heat moves through.") as tracker:
            sub = self.show_subtitle("Now, what about the cup's layers? If they don't touch much, less heat moves through.")
            self.play(FadeOut(in_rays, shift=LEFT * 0.3), FadeOut(reflected_rays, shift=LEFT * 0.3),
                      FadeOut(radiation_label, shift=DOWN * 0.2), FadeOut(bulb, shift=UP * 0.3),
                      FadeOut(bulb_rays, shift=UP * 0.3), run_time=0.9, rate_func=rush_into)
            self.play(AnimationGroup(Create(shell_outer), Create(shell_gap), Create(shell_inner), lag_ratio=0.25),
                      AnimationGroup(*[FadeIn(t, shift=RIGHT * 0.5) for t in legend], lag_ratio=0.25),
                      run_time=2.4, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 3.9))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="This keeps your drink at the right temperature.") as tracker:
            sub = self.show_subtitle("This keeps your drink at the right temperature.")
            self.play(FadeOut(legend, shift=RIGHT * 0.4), FadeOut(mirrors),
                      shells.animate.move_to(ORIGIN), cup.animate.move_to(ORIGIN),
                      run_time=1.2, rate_func=smooth)
            self.play(shell_outer.animate.shift(LEFT * 2.1), shell_inner.animate.shift(RIGHT * 2.1),
                      GrowArrow(gap_arrow_L), GrowArrow(gap_arrow_R),
                      FadeIn(vacuum_text.shift(UP * 0.4), shift=UP * 0.2),
                      run_time=2.0, rate_func=smooth)
            self.play(GrowArrow(conduction_path), run_time=0.9)
            self.play(FadeIn(conduction_cross, scale=1.4), run_time=0.6)
            self.wait(max(0.1, tracker.duration - 3.2))
            self.play(shell_outer.animate.shift(RIGHT * 2.1), shell_inner.animate.shift(LEFT * 2.1),
                      FadeOut(gap_arrow_L), FadeOut(gap_arrow_R),
                      FadeOut(conduction_path), FadeOut(conduction_cross),
                      run_time=1.6, rate_func=smooth)
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="We test our cup in bright light and regular conditions.") as tracker:
            sub = self.show_subtitle("We test our cup in bright light and regular conditions.")
            self.play(FadeOut(shells, shift=UP * 0.3), FadeOut(vacuum_text, shift=DOWN * 0.3),
                      cup.animate.scale(0.62).move_to(cup_start_b7),
                      run_time=1.1, rate_func=rush_into)
            self.play(Create(bench), GrowArrow(weight_arrow), GrowArrow(normal_arrow),
                      run_time=1.1, rate_func=smooth)
            self.play(cup.animate.move_to(bench_right_seat),
                      weight_arrow.animate.shift(bench_delta),
                      normal_arrow.animate.shift(bench_delta),
                      run_time=1.6, rate_func=smooth)
            self.play(FadeIn(plain_cup, shift=UP * 0.4),
                      FadeIn(label_A), FadeIn(label_B),
                      run_time=1.0, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 4.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Does it keep the drink cool?") as tracker:
            sub = self.show_subtitle("Does it keep the drink cool?")
            self.play(FadeOut(weight_arrow), FadeOut(normal_arrow),
                      FadeIn(therm_A, shift=DOWN * 0.4), FadeIn(therm_B, shift=DOWN * 0.4),
                      run_time=1.2, rate_func=smooth)
            self.play(FadeIn(merc_A), FadeIn(merc_B), FadeIn(read_A), FadeIn(read_B),
                      run_time=1.0, rate_func=smooth)
            self.play(temp_A_tracker.animate.set_value(41.0),
                      temp_B_tracker.animate.set_value(84.0),
                      merc_A.animate.stretch_to_fit_height(0.32, about_edge=DOWN),
                      merc_B.animate.stretch_to_fit_height(0.81, about_edge=DOWN),
                      AnimationGroup(*[GrowArrow(a) for a in loss_arrows], lag_ratio=0.2),
                      run_time=3.5, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 1.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Using fewer materials is smart. It saves money and helps the environment.") as tracker:
            sub = self.show_subtitle("Using fewer materials is smart. It saves money and helps the environment.")
            self.play(FadeOut(therm_A, shift=DOWN * 0.3), FadeOut(therm_B, shift=DOWN * 0.3),
                      FadeOut(read_A), FadeOut(read_B), FadeOut(merc_A), FadeOut(merc_B),
                      FadeOut(loss_arrows), FadeOut(plain_cup), FadeOut(bench),
                      FadeOut(label_A), FadeOut(label_B), FadeOut(cup),
                      run_time=0.9, rate_func=rush_into)
            self.play(GrowFromEdge(bar_L, DOWN), FadeIn(label_L, shift=UP * 0.2), FadeIn(count_num),
                      run_time=1.2, rate_func=smooth)
            self.play(GrowArrow(reduction_arrow), run_time=0.8)
            self.play(count_tracker.animate.set_value(1),
                      bar_L.animate.stretch_to_fit_height(0.5, about_edge=DOWN),
                      GrowFromEdge(bar_R, DOWN), FadeIn(label_R, shift=UP * 0.2),
                      run_time=2.0, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 4.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Small changes like this add up for our whole planet.") as tracker:
            sub = self.show_subtitle("Small changes like this add up for our whole planet.")
            cup.move_to(np.array([-3.3, 0.0, 0]))
            self.play(FadeOut(bar_L, shift=DOWN * 0.3), FadeOut(bar_R, shift=DOWN * 0.3),
                      FadeOut(label_L), FadeOut(label_R), FadeOut(count_num),
                      FadeOut(reduction_arrow),
                      FadeIn(cup),
                      run_time=1.0, rate_func=smooth)
            self.play(DrawBorderThenFill(earth_globe),
                      AnimationGroup(GrowFromCenter(cont1), GrowFromCenter(cont2), GrowFromCenter(cont3), lag_ratio=0.25),
                      FadeIn(orbit_circle), run_time=1.6, rate_func=smooth)
            self.play(MoveAlongPath(orbit_dot, orbit_circle), FadeIn(co2_text, shift=UP * 0.2),
                      run_time=2.4, rate_func=linear)
            self.wait(max(0.1, tracker.duration - 4.2))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So, a well-designed cup reflects light and has layers that don't touch much.") as tracker:
            sub = self.show_subtitle("So, a well-designed cup reflects light and has layers that don't touch much.")
            self.play(FadeOut(earth, shift=RIGHT * 0.4), FadeOut(orbit_circle), FadeOut(orbit_dot),
                      FadeOut(co2_text, shift=DOWN * 0.3),
                      cup.animate.scale(0.75).move_to(np.array([-4.4, 0.0, 0])),
                      run_time=1.0, rate_func=rush_into)
            self.play(Write(headline), run_time=1.2, rate_func=smooth)
            self.play(FadeIn(pct_num), FadeIn(pct_suffix), run_time=0.6)
            self.play(pct_tracker.animate.set_value(98), run_time=1.5, rate_func=rush_from)
            self.play(Flash(pct_num, color=C_GOLD, num_lines=16, line_length=0.3), run_time=0.7)
            self.wait(max(0.1, tracker.duration - 4.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="It performs well and uses less material.") as tracker:
            sub = self.show_subtitle("It performs well and uses less material.")
            self.play(FadeOut(headline, shift=UP * 0.3), FadeOut(pct_num, shift=DOWN * 0.3),
                      FadeOut(pct_suffix, shift=DOWN * 0.3), run_time=0.9, rate_func=rush_into)
            self.play(cup.animate.move_to(ORIGIN).scale(1.35), run_time=1.5, rate_func=smooth)
            self.play(AnimationGroup(Create(check_circle), Create(check), lag_ratio=0.25),
                      run_time=1.1, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 2.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Next time you see a cup, think about how it's designed to work so well with so little!") as tracker:
            sub = self.show_subtitle("Next time you see a cup, think about how it's designed to work so well with so little!")
            self.play(question.animate.scale(1.5).move_to(UP * 2.4).set_color(C_GOLD),
                      run_time=1.4, rate_func=smooth)
            self.play(FadeIn(final_check_math.next_to(question, RIGHT, buff=0.35), shift=UP * 0.2),
                      run_time=0.7, rate_func=smooth)
            self.play(FadeIn(tagline, shift=UP * 0.2), run_time=1.1, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 3.6))
            self.play(FadeOut(cup), FadeOut(check), FadeOut(check_circle), FadeOut(question),
                      FadeOut(final_check_math), FadeOut(tagline), FadeOut(sub),
                      run_time=1.4, rate_func=smooth)