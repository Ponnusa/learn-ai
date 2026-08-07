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




class WhyDoesTheCupKeepItHot(VoiceoverScene):
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

        # ═══ SETUP BLOCK: define every object used later so nothing crashes ═══
        # VMobject is used in the animation code as an empty vectorized placeholder
        # (e.g. `cut_line = VMobject()`). VGroup is a fully compatible stand-in
        # since it is itself a VMobject subclass and supports the same empty
        # construction/usage pattern used below.
        VMobject = VGroup
        # ═══ END SETUP BLOCK ═══

        self.camera.background_color = ManimColor("#0D1117")

        STEEL = ManimColor("#8FA3B0")
        HEAT = ManimColor("#FF6B4A")
        WIN = ManimColor("#4CD97B")

        background = Rectangle(width=15, height=9, fill_color=ManimColor("#0D1117"),
                                fill_opacity=1, stroke_width=0)
        table_line = Line(np.array([-7, -2.2, 0]), np.array([7, -2.2, 0]), color=GRAY_B, stroke_width=3)

        outer_shell = Polygon(np.array([-1.1, -1.6, 0]), np.array([1.1, -1.6, 0]),
                               np.array([1.0, 1.4, 0]), np.array([-1.0, 1.4, 0]),
                               stroke_width=4, color=STEEL, fill_color=STEEL, fill_opacity=0.3)
        inner_liquid = Polygon(np.array([-0.8, -1.3, 0]), np.array([0.8, -1.3, 0]),
                                np.array([0.75, 0.9, 0]), np.array([-0.75, 0.9, 0]),
                                stroke_width=0, fill_color=HEAT, fill_opacity=0.8)
        CUP = VGroup(outer_shell, inner_liquid).move_to(RIGHT * 8)

        lid_body = Rectangle(width=2.3, height=0.35, fill_color=STEEL, fill_opacity=0.6,
                              stroke_width=3, stroke_color=WHITE)
        lid_knob = Circle(radius=0.12, fill_color=STEEL, fill_opacity=0.8,
                           stroke_width=2, stroke_color=WHITE).next_to(lid_body, UP, buff=0.02)
        lid_group = VGroup(lid_body, lid_knob).move_to(np.array([-3.0, 4.8, 0]))

        gravity_arrow = Arrow(start=np.array([0, -1.6, 0]), end=np.array([0, -2.6, 0]), color=RED, buff=0)
        gravity_label = Text("mg", font_size=24, color=RED).next_to(gravity_arrow, DOWN, buff=0.1)
        normal_arrow = Arrow(start=np.array([0.6, -2.6, 0]), end=np.array([0.6, -1.6, 0]), color=BLUE, buff=0)
        normal_label = Text("N", font_size=24, color=BLUE).next_to(normal_arrow, RIGHT, buff=0.1)
        statics_group = VGroup(gravity_arrow, gravity_label, normal_arrow, normal_label)

        thermometer = get_svg("thermometer", height=1.0).move_to(np.array([2.6, 0.5, 0]))
        temp_start_label = Text("72°F", font_size=22, color=WHITE).next_to(thermometer, UP, buff=0.15)
        steam = VGroup(*[
            ArcBetweenPoints(np.array([-0.3 + i * 0.3, 1.5, 0]), np.array([-0.1 + i * 0.3, 2.3, 0]),
                              angle=-PI / 3, stroke_width=2, color=GRAY_B)
            for i in range(3)
        ])

        hook_title = Text("Why does your cup keep drinks hot?", font_size=30, color=WHITE).move_to(np.array([0, 3.0, 0]))
        ghost_cup = VGroup(
            Polygon(np.array([-1.0, -1.4, 0]), np.array([1.0, -1.4, 0]),
                    np.array([0.9, 1.2, 0]), np.array([-0.9, 1.2, 0]),
                    stroke_width=3, color=GRAY_B, fill_color=GRAY_B, fill_opacity=0.15)
        ).move_to(np.array([3.4, -0.2, 0]))
        curved_arrow = CurvedArrow(np.array([-1.0, 0, 0]), np.array([1.8, 0, 0]), color=YELLOW)
        question_mark = Text("?", font_size=60, color=YELLOW).move_to(np.array([3.4, 1.6, 0]))

        divider = Rectangle(width=0.12, height=2.6, fill_color=GRAY_B, fill_opacity=0.5,
                             stroke_width=0).move_to(np.array([-3.0, 0.0, 0]))
        _cut_s, _cut_e = np.array([-4.4, -1.9, 0]), np.array([-1.6, 1.9, 0])
        if np.linalg.norm(_cut_e - _cut_s) > 0.01:
            cut_line = DashedLine(_cut_s, _cut_e, color=WHITE, stroke_width=2)
        else:
            cut_line = VMobject()

        outer_hl = Line(np.array([-4.2, -1.7, 0]), np.array([-4.2, 1.7, 0]), color=STEEL, stroke_width=6)
        inner_hl = Line(np.array([-1.9, -1.5, 0]), np.array([-1.9, 1.5, 0]), color=HEAT, stroke_width=6)
        gap_fill = Rectangle(width=0.5, height=3.2, fill_color=BLUE_E, fill_opacity=0.0,
                              stroke_width=0).move_to(np.array([-3.0, 0.0, 0]))
        gap_label = Text("Insulating air gap", font_size=22, color=WHITE).move_to(np.array([-3.0, -2.6, 0]))
        gap_pointer = Arrow(np.array([-3.0, -2.3, 0]), np.array([-3.0, -1.5, 0]), color=WHITE, buff=0)
        cond_arrows = VGroup(*[
            Arrow(np.array([-4.2 + i * 0.9, -1.8, 0]), np.array([-4.2 + i * 0.9, 1.8, 0]),
                  color=ORANGE, buff=0, stroke_width=3)
            for i in range(4)
        ])

        escape_arrow = Arrow(np.array([-3.0, 1.5, 0]), np.array([-3.0, 3.0, 0]), color=RED, buff=0)
        lid_label = Text("Lid traps heat", font_size=22, color=WHITE).move_to(np.array([-3.0, -2.6, 0]))

        steel_row = Text("Stainless Steel", font_size=22, color=WHITE).move_to(np.array([2.5, 1.3, 0]))
        glass_row = Text("Glass", font_size=22, color=WHITE).move_to(np.array([2.5, 0.5, 0]))
        copper_row = Text("Copper", font_size=22, color=WHITE).move_to(np.array([2.5, -0.3, 0]))
        spec_panel = VGroup(steel_row, glass_row, copper_row)
        conduction_formula = MathTex(r"Q = kA\frac{\Delta T}{d}", font_size=32, color=WHITE).move_to(np.array([2.5, -1.4, 0]))
        flying_swatch = Square(side_length=0.5, fill_color=STEEL, fill_opacity=0.8,
                                stroke_width=2).move_to(np.array([2.5, 1.3, 0]))

        mirror_left = Rectangle(width=0.2, height=2.6, fill_color=GRAY_A, fill_opacity=0.9,
                                 stroke_width=1).move_to(np.array([-4.2, 0, 0]))
        mirror_right = Rectangle(width=0.2, height=2.6, fill_color=GRAY_A, fill_opacity=0.9,
                                  stroke_width=1).move_to(np.array([-1.8, 0, 0]))
        mirror_strips = VGroup(mirror_left, mirror_right)
        ray_paths = VGroup(
            Line(np.array([-4.0, 0.8, 0]), np.array([-2.0, 0.8, 0]), color=YELLOW, stroke_width=2),
            Line(np.array([-4.0, 0.0, 0]), np.array([-2.0, 0.0, 0]), color=YELLOW, stroke_width=2),
            Line(np.array([-4.0, -0.8, 0]), np.array([-2.0, -0.8, 0]), color=YELLOW, stroke_width=2),
        )
        ray_dots = VGroup(*[Dot(radius=0.06, color=YELLOW) for _ in range(3)])
        radiation_label = Text("Reflective surfaces bounce heat", font_size=20, color=WHITE).move_to(np.array([-3.0, -2.6, 0]))

        foam = VGroup(*[
            Circle(radius=0.12, fill_color=GRAY_B, fill_opacity=0.6, stroke_width=1).move_to(
                np.array([-3.8 + (i % 4) * 0.55, 1.2 - (i // 4) * 0.5, 0]))
            for i in range(12)
        ])
        foam_label = Text("Foam traps air pockets", font_size=20, color=WHITE).move_to(np.array([-3.0, -2.6, 0]))
        base_arrow = Arrow(np.array([-3.0, -1.8, 0]), np.array([-3.0, -0.3, 0]), color=ORANGE, buff=0)

        gasket = Ellipse(width=2.2, height=0.3, fill_color=RED_E, fill_opacity=0.7,
                          stroke_width=2).move_to(np.array([-3.0, 1.9, 0]))
        down_press = Arrow(np.array([-3.0, 2.6, 0]), np.array([-3.0, 2.0, 0]), color=WHITE, buff=0)
        up_press = Arrow(np.array([-3.0, 1.2, 0]), np.array([-3.0, 1.8, 0]), color=WHITE, buff=0)
        gasket_label = Text("Tight seal locks in heat", font_size=20, color=WHITE).move_to(np.array([-3.0, -2.6, 0]))

        insight = Text("Insulation is teamwork.", font_size=28, color=WHITE).move_to(np.array([0, 1.0, 0]))
        chips = VGroup(*[
            Square(side_length=0.35, fill_color=YELLOW, fill_opacity=0.8, stroke_width=1).move_to(
                np.array([-2.0 + i * 1.3, -0.5, 0]))
            for i in range(4)
        ])
        insight_result = Text("Together they keep it hot.", font_size=26, color=WIN).move_to(np.array([0, -1.4, 0]))
        insight_box = Rectangle(width=5.2, height=0.9, color=WIN, stroke_width=2).move_to(np.array([0, -1.4, 0]))

        thermometer2 = get_svg("thermometer", height=2.2).move_to(np.array([4.6, -0.5, 0]))
        mercury = Rectangle(width=0.18, height=1.2, fill_color=RED, fill_opacity=1.0,
                             stroke_width=0).move_to(np.array([4.6, -1.0, 0]))
        temp = Text("72", font_size=26, color=WHITE).move_to(np.array([4.6, 1.4, 0]))
        temp_unit = Text("°F", font_size=22, color=WHITE).next_to(temp, RIGHT, buff=0.05)
        clock = Circle(radius=0.4, color=WHITE, stroke_width=2).move_to(np.array([-4.6, 1.4, 0]))
        temp_tracker = ValueTracker(72.0)
        delta_label = Text("Still warm after hours", font_size=20, color=WHITE).move_to(np.array([0, -2.6, 0]))

        self.add(background, CUP, lid_group, gap_fill)

        final_title = Text("6 hours later…", font_size=28, color=WHITE).move_to(np.array([0, 3.0, 0]))
        ghost_shell2 = Polygon(np.array([-1.45, -2.10, 0]), np.array([1.45, -2.10, 0]),
                               np.array([1.30, 1.90, 0]), np.array([-1.30, 1.90, 0]),
                               stroke_width=4, color=STEEL, fill_color=STEEL, fill_opacity=0.25)
        ghost_liquid2 = Polygon(np.array([-1.02, -1.72, 0]), np.array([1.02, -1.72, 0]),
                                np.array([0.99, 1.10, 0]), np.array([-0.99, 1.10, 0]),
                                stroke_width=0, fill_color=HEAT, fill_opacity=0.75)
        ghost_cup2 = VGroup(ghost_shell2, ghost_liquid2).move_to(np.array([3.4, -0.2, 0]))
        final_line = Text("Still hot. That's why.", font_size=30, color=WIN)
        final_line.move_to(np.array([0, -2.0, 0]))

        self.add(table_line)
        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Imagine sipping your morning coffee, and it stays hot for hours. How does that happen?") as tracker:
            sub = self.show_subtitle("Imagine sipping your morning coffee, and it stays hot for hours. How does that happen?")
            self.play(Create(table_line), rate_func=smooth, run_time=1.0)
            self.play(CUP.animate.move_to(ORIGIN), rate_func=smooth, run_time=2.0)
            self.play(FadeIn(thermometer, shift=RIGHT * 0.6), rate_func=rush_from, run_time=1.2)
            self.play(FadeIn(temp_start_label, shift=UP * 0.2), Create(steam, lag_ratio=0.3),
                      rate_func=smooth, run_time=1.4)
            self.play(AnimationGroup(GrowArrow(gravity_arrow), FadeIn(gravity_label),
                                     GrowArrow(normal_arrow), FadeIn(normal_label), lag_ratio=0.2),
                      rate_func=smooth, run_time=1.6)
            self.wait(max(0.1, tracker.duration - 8.0))
            self.play(FadeOut(statics_group, shift=DOWN * 0.2), rate_func=rush_into, run_time=0.8)
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="What makes a cup so good at keeping your drink at the perfect temperature?") as tracker:
            sub = self.show_subtitle("What makes a cup so good at keeping your drink at the perfect temperature?")
            self.play(FadeOut(thermometer, temp_start_label, steam, shift=RIGHT * 0.5),
                      rate_func=rush_into, run_time=0.9)
            self.play(FadeIn(hook_title, shift=DOWN * 0.4), rate_func=smooth, run_time=1.0)
            self.play(CUP.animate.shift(LEFT * 3.8), rate_func=smooth, run_time=1.2)
            self.play(FadeIn(ghost_cup, shift=RIGHT * 0.8), rate_func=rush_from, run_time=1.3)
            self.play(Create(curved_arrow), rate_func=smooth, run_time=1.3)
            self.play(DrawBorderThenFill(question_mark), rate_func=smooth, run_time=1.5)
            self.wait(max(0.1, tracker.duration - 8.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Let's start with double walls. They create an insulating layer, like a cozy blanket for your drink, reducing heat transfer.") as tracker:
            sub = self.show_subtitle("Let's start with double walls. They create an insulating layer, like a cozy blanket for your drink, reducing heat transfer.")
            self.play(FadeOut(ghost_cup, question_mark, curved_arrow, hook_title, shift=DOWN * 0.3),
                      rate_func=rush_into, run_time=1.0)
            self.play(CUP.animate.move_to(np.array([-3.0, 0.0, 0])).scale(1.25),
                      FadeIn(divider), rate_func=smooth, run_time=1.5)
            self.play(Create(cut_line), rate_func=smooth, run_time=1.0)
            self.play(AnimationGroup(Create(outer_hl), Create(inner_hl),
                                     gap_fill.animate.set_opacity(1.0), lag_ratio=0.25),
                      rate_func=smooth, run_time=2.4)
            self.play(FadeIn(gap_label, shift=LEFT * 0.3), GrowArrow(gap_pointer),
                      rate_func=smooth, run_time=1.2)
            self.play(AnimationGroup(*[GrowArrow(a) for a in cond_arrows], lag_ratio=0.25),
                      rate_func=smooth, run_time=1.4)
            self.play(cond_arrows.animate.set_opacity(0.2), rate_func=rush_into, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 10.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Then there's the lid. It traps heat inside, like a little greenhouse, keeping your drink warm or cold.") as tracker:
            sub = self.show_subtitle("Then there's the lid. It traps heat inside, like a little greenhouse, keeping your drink warm or cold.")
            self.play(FadeOut(gap_pointer, shift=RIGHT * 0.2), rate_func=rush_into, run_time=0.6)
            self.play(GrowArrow(escape_arrow), rate_func=smooth, run_time=1.2)
            self.play(lid_group.animate.move_to(np.array([-3.0, 2.05, 0])),
                      rate_func=rush_into, run_time=1.3)
            self.play(Flash(lid_group, color=WHITE, line_length=0.2, num_lines=12), run_time=0.8)
            self.play(escape_arrow.animate.set_opacity(0.15).scale(0.4, about_edge=DOWN),
                      rate_func=smooth, run_time=1.0)
            self.play(FadeIn(lid_label, shift=LEFT * 0.3), rate_func=smooth, run_time=1.2)
            self.wait(max(0.1, tracker.duration - 7.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="The material of the cup matters too. Stainless steel or certain plastics act like shields, preventing heat from escaping.") as tracker:
            sub = self.show_subtitle("The material of the cup matters too. Stainless steel or certain plastics act like shields, preventing heat from escaping.")
            self.play(FadeOut(gap_label, lid_label, shift=RIGHT * 0.3), rate_func=rush_into, run_time=0.8)
            self.play(AnimationGroup(FadeIn(steel_row, shift=LEFT * 0.5),
                                     FadeIn(glass_row, shift=LEFT * 0.5),
                                     FadeIn(copper_row, shift=LEFT * 0.5), lag_ratio=0.25),
                      rate_func=smooth, run_time=2.2)
            self.play(FadeIn(conduction_formula, shift=UP * 0.2), rate_func=smooth, run_time=1.4)
            self.play(Indicate(conduction_formula, scale_factor=1.1, color=YELLOW), run_time=0.8)
            self.play(Indicate(steel_row, scale_factor=1.15, color=YELLOW), run_time=1.0)
            self.play(copper_row.animate.set_opacity(0.25), rate_func=smooth, run_time=1.0)
            self.play(FadeIn(flying_swatch), rate_func=smooth, run_time=0.5)
            self.play(flying_swatch.animate.move_to(np.array([-4.6, 0.0, 0])).scale(0.5),
                      rate_func=smooth, run_time=1.3)
            self.play(FadeOut(flying_swatch), outer_shell.animate.set_fill(STEEL, 0.4),
                      rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 10.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Reflective surfaces are like mirrors, bouncing heat away and keeping your drink cooler.") as tracker:
            sub = self.show_subtitle("Reflective surfaces are like mirrors, bouncing heat away and keeping your drink cooler.")
            self.play(FadeOut(spec_panel, conduction_formula, shift=RIGHT * 0.4),
                      rate_func=rush_into, run_time=1.0)
            self.play(AnimationGroup(GrowFromCenter(mirror_left), GrowFromCenter(mirror_right),
                                     lag_ratio=0.25), rate_func=smooth, run_time=1.6)
            self.play(Create(ray_paths, lag_ratio=0.2), FadeIn(ray_dots), rate_func=smooth, run_time=1.4)
            self.play(AnimationGroup(*[MoveAlongPath(d, p) for d, p in zip(ray_dots, ray_paths)],
                                     lag_ratio=0.2), rate_func=smooth, run_time=1.8)
            self.play(FadeIn(radiation_label, shift=LEFT * 0.3), rate_func=smooth, run_time=1.2)
            self.wait(max(0.1, tracker.duration - 7.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Foam or porous materials are like tiny air pockets, slowing down heat conduction.") as tracker:
            sub = self.show_subtitle("Foam or porous materials are like tiny air pockets, slowing down heat conduction.")
            self.play(FadeOut(ray_dots, ray_paths, radiation_label, shift=RIGHT * 0.3),
                      rate_func=rush_into, run_time=0.9)
            self.play(AnimationGroup(*[GrowFromCenter(b) for b in foam], lag_ratio=0.02),
                      rate_func=smooth, run_time=2.2)
            self.play(FadeIn(foam_label, shift=LEFT * 0.3), rate_func=smooth, run_time=1.2)
            self.play(GrowArrow(base_arrow), rate_func=smooth, run_time=1.0)
            self.play(base_arrow.animate.set_color(GRAY).scale(0.35, about_edge=UP),
                      Indicate(foam, color=YELLOW, scale_factor=1.05), rate_func=smooth, run_time=1.2)
            self.wait(max(0.1, tracker.duration - 7.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="And a tight seal? It's like closing the door to keep the warmth in.") as tracker:
            sub = self.show_subtitle("And a tight seal? It's like closing the door to keep the warmth in.")
            self.play(FadeOut(foam_label, base_arrow, shift=RIGHT * 0.3), rate_func=rush_into, run_time=0.8)
            self.play(DrawBorderThenFill(gasket), rate_func=smooth, run_time=1.3)
            self.play(AnimationGroup(GrowArrow(down_press), GrowArrow(up_press), lag_ratio=0.25),
                      rate_func=smooth, run_time=1.2)
            self.play(lid_group.animate.shift(DOWN * 0.10), gasket.animate.set_color(WIN),
                      rate_func=smooth, run_time=1.0)
            self.play(Flash(gasket, color=WHITE, line_length=0.2, num_lines=12), run_time=0.7)
            self.play(FadeIn(gasket_label, shift=LEFT * 0.3),
                      FadeOut(escape_arrow, shift=UP * 0.3), rate_func=smooth, run_time=1.2)
            self.wait(max(0.1, tracker.duration - 7.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Each feature plays a role in the symphony of insulation, working together to maintain your drink's temperature.") as tracker:
            sub = self.show_subtitle("Each feature plays a role in the symphony of insulation, working together to maintain your drink's temperature.")
            self.play(FadeOut(gasket_label, down_press, up_press, cond_arrows, outer_hl, inner_hl,
                              cut_line, shift=DOWN * 0.3), rate_func=rush_into, run_time=1.2)
            self.play(FadeIn(insight, shift=UP * 0.3), rate_func=smooth, run_time=2.0)
            self.wait(0.6)
            self.play(Indicate(insight, scale_factor=1.15, color=YELLOW), run_time=1.4)
            self.play(FadeIn(chips, shift=UP * 0.2), rate_func=smooth, run_time=1.2)
            self.play(AnimationGroup(*[Indicate(c, scale_factor=1.8) for c in chips], lag_ratio=0.3),
                      run_time=1.6)
            self.play(FadeIn(insight_result, shift=UP * 0.2), Create(insight_box),
                      rate_func=smooth, run_time=1.6)
            self.wait(max(0.1, tracker.duration - 10.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So, the next time you enjoy a perfectly hot or cold drink, remember the science behind your cup.") as tracker:
            sub = self.show_subtitle("So, the next time you enjoy a perfectly hot or cold drink, remember the science behind your cup.")
            self.play(FadeOut(insight, insight_result, insight_box, chips, shift=RIGHT * 0.4),
                      rate_func=rush_into, run_time=1.1)
            self.play(FadeIn(thermometer2, shift=LEFT * 0.7), FadeIn(mercury),
                      rate_func=smooth, run_time=1.3)
            self.play(FadeIn(temp), FadeIn(temp_unit), FadeIn(clock, shift=UP * 0.2),
                      rate_func=smooth, run_time=1.0)
            self.play(temp_tracker.animate.set_value(88.0),
                      mercury.animate.stretch_to_fit_height(1.88).shift(DOWN * 0.06),
                      rate_func=linear, run_time=3.5)
            self.play(Circumscribe(temp, color=WIN, buff=0.2), run_time=1.5)
            self.play(FadeIn(delta_label, shift=UP * 0.2), rate_func=smooth, run_time=1.3)
            self.wait(max(0.1, tracker.duration - 10.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="It's not just a cup; it's a marvel of design and physics.") as tracker:
            sub = self.show_subtitle("It's not just a cup; it's a marvel of design and physics.")
            self.play(FadeOut(thermometer2, temp, temp_unit, mercury, clock, delta_label,
                              foam, gasket, divider, escape_arrow, shift=DOWN * 0.3),
                      rate_func=rush_into, run_time=1.3)
            self.play(gap_fill.animate.set_opacity(0.0), mirror_strips.animate.set_opacity(0.0),
                      rate_func=smooth, run_time=1.2)
            self.play(CUP.animate.scale(0.85).move_to(np.array([-3.4, -0.2, 0])),
                      lid_group.animate.scale(0.85).shift(DOWN * 0.35 + LEFT * 0.4),
                      rate_func=smooth, run_time=1.4)
            self.play(FadeIn(final_title, shift=DOWN * 0.3), FadeIn(ghost_cup2, shift=LEFT * 0.5),
                      rate_func=smooth, run_time=1.5)
            self.play(FadeIn(final_line, shift=UP * 0.2), rate_func=smooth, run_time=1.4)
            self.wait(max(0.1, tracker.duration - 7.5))
            self.play(FadeOut(sub), run_time=0.4)