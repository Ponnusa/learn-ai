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



class WhyCoffeeStaysHot(VoiceoverScene):
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

        # ═══ SETUP BLOCK: define every mobject used below ═══
        background = Rectangle(width=config.frame_width, height=config.frame_height)
        background.set_fill(ManimColor("#0D1117"), opacity=1).set_stroke(width=0)
        divider = Line(LEFT * 6.5, RIGHT * 6.5, stroke_opacity=0)

        title = Text("Why Coffee Stays Hot", font_size=36, color=WHITE).to_edge(UP, buff=0.4)

        # cup + steam
        cup_body = Rectangle(width=1.6, height=1.4, color=ManimColor("#B08968"), fill_opacity=0.9, stroke_color=WHITE)
        cup_body.move_to(DOWN * 0.5)
        cup_handle = Arc(radius=0.35, start_angle=-PI / 2, angle=PI, color=WHITE)
        cup_handle.next_to(cup_body, RIGHT, buff=-0.05)
        steam = VGroup(*[
            Line(ORIGIN, UP * 0.5, color=ManimColor("#CCCCCC"), stroke_width=2).shift(cup_body.get_top() + UP * 0.2 + RIGHT * dx)
            for dx in [-0.3, 0, 0.3]
        ])
        cup_group = VGroup(cup_body, cup_handle, steam)

        grav_arrow = Arrow(cup_body.get_bottom(), cup_body.get_bottom() + DOWN * 0.9, color=ManimColor("#4FC3F7"), buff=0.05)
        grav_label = Text("mg", font_size=24, color=ManimColor("#4FC3F7")).next_to(grav_arrow, RIGHT, buff=0.1)

        thermo = get_svg("thermometer", height=1.0).next_to(cup_body, LEFT, buff=0.6)
        temp_start = Text("95°C", font_size=28, color=ManimColor("#FFD166")).next_to(thermo, UP, buff=0.15)

        question_text = Text("Where does the heat go?", font_size=28, color=WHITE).shift(UP * 1.8)
        qcircle = Circle(radius=0.5, color=ManimColor("#EF476F")).move_to(UP * 0.4)
        qmark = Text("?", font_size=40, color=ManimColor("#EF476F")).move_to(qcircle.get_center())
        heat_q = Text("Heat", font_size=24, color=WHITE).next_to(qcircle, DOWN, buff=0.2)
        leak_arrows = VGroup(*[
            Arrow(qcircle.get_center(), qcircle.get_center() + vec, color=ManimColor("#EF476F"), buff=0.1)
            for vec in [UP * 1.2 + LEFT * 0.6, UP * 1.4, UP * 1.2 + RIGHT * 0.6]
        ])

        gap_region = Rectangle(width=1.9, height=1.6, color=ManimColor("#4FC3F7"), fill_opacity=0.15, stroke_opacity=0.4)
        gap_region.move_to(cup_body.get_center())
        inner_wall = Rectangle(width=1.3, height=1.2, color=WHITE, stroke_width=2)
        inner_wall.move_to(cup_body.get_center())
        wall_pointer = Arrow(RIGHT * 2.5 + UP * 0.3, inner_wall.get_right(), color=WHITE, buff=0.1)
        wall_label = Text("air / vacuum gap", font_size=22, color=WHITE).next_to(wall_pointer, RIGHT, buff=0.1)
        gap_dots = VGroup(*[
            Dot(radius=0.04, color=ManimColor("#4FC3F7")).move_to(
                cup_body.get_center() + np.array([np.random.uniform(-0.7, 0.7), np.random.uniform(-0.6, 0.6), 0])
            ) for _ in range(10)
        ])
        cond_arrow = Arrow(cup_body.get_left() + LEFT * 0.1, cup_body.get_left() + LEFT * 1.3, color=ManimColor("#EF476F"), buff=0.05)
        block_cross = VGroup(
            Line(UL * 0.15, DR * 0.15, color=ManimColor("#EF476F"), stroke_width=4),
            Line(DL * 0.15, UR * 0.15, color=ManimColor("#EF476F"), stroke_width=4),
        ).move_to(cond_arrow.get_center())
        vacuum_label = Text("less heat transfer", font_size=22, color=WHITE).next_to(cond_arrow, DOWN, buff=0.3)

        silver_layer = Rectangle(width=1.5, height=1.3, color=ManimColor("#C0C0C0"), fill_opacity=0.5, stroke_color=WHITE)
        silver_layer.move_to(cup_body.get_center())
        mirror_pointer = Arrow(RIGHT * 2.5 + DOWN * 0.3, silver_layer.get_right(), color=WHITE, buff=0.1)
        mirror_label = Text("shiny surface", font_size=22, color=WHITE).next_to(mirror_pointer, RIGHT, buff=0.1)
        sweep = Rectangle(width=1.5, height=0.15, color=WHITE, fill_opacity=0.6, stroke_opacity=0)
        sweep.move_to(silver_layer.get_top())

        normal_line = DashedLine(UP * 1.6 + LEFT * 3, DOWN * 0.4 + LEFT * 3, color=GRAY)
        incoming_rays = VGroup(*[
            Arrow(LEFT * 4.5 + UP * (1.6 - i * 0.5), LEFT * 3 + UP * (0.6 - i * 0.2), color=ManimColor("#FFD166"), buff=0.05)
            for i in range(3)
        ])
        reflected_rays = VGroup(*[
            Arrow(LEFT * 3 + UP * (0.6 - i * 0.2), LEFT * 1.5 + UP * (1.6 - i * 0.5), color=ManimColor("#FFD166"), buff=0.05)
            for i in range(3)
        ])
        photon = Dot(color=ManimColor("#FFD166")).move_to(incoming_rays[1].get_start())
        v_path = VMobject(color=ManimColor("#FFD166"))
        v_path.set_points_as_corners([incoming_rays[1].get_start(), incoming_rays[1].get_end(), reflected_rays[1].get_end()])
        theta_tex = MathTex(r"\theta_i = \theta_r", color=WHITE, font_size=32).shift(LEFT * 3 + UP * 2.2)

        magnifier = VGroup(
            Circle(radius=0.35, color=WHITE, stroke_width=3),
            Line(RIGHT * 0.25, RIGHT * 0.6, color=WHITE, stroke_width=3).shift(DOWN * 0.25 + RIGHT * 0.25),
        ).move_to(UP * 1.5 + LEFT * 3)
        connector_lines = VGroup(
            Line(magnifier.get_bottom(), DOWN * 0.5 + LEFT * 1.2, color=GRAY, stroke_width=1.5),
            Line(magnifier.get_bottom(), DOWN * 0.5 + LEFT * 0.2, color=GRAY, stroke_width=1.5),
        )
        foam_block = Rectangle(width=2.2, height=1.6, color=ManimColor("#B08968"), fill_opacity=0.6, stroke_color=WHITE)
        foam_block.move_to(DOWN * 0.4)
        pores = VGroup(*[
            Circle(radius=0.09, color=ManimColor("#4FC3F7"), fill_opacity=0.5, stroke_width=1).move_to(
                foam_block.get_center() + np.array([x, y, 0])
            ) for x in [-0.6, 0, 0.6] for y in [-0.4, 0.3]
        ])
        foam_label = Text("trapped air pockets", font_size=22, color=WHITE).next_to(foam_block, DOWN, buff=0.3)

        zigzag = VMobject(color=ManimColor("#EF476F"))
        zigzag.set_points_as_corners([
            foam_block.get_left() + LEFT * 0.3,
            foam_block.get_left() + UP * 0.4,
            foam_block.get_center() + DOWN * 0.3,
            foam_block.get_right() + UP * 0.2,
            foam_block.get_right() + RIGHT * 0.3,
        ])
        heat_dot = Dot(color=ManimColor("#EF476F")).move_to(zigzag.get_start())
        straight_arrow = Arrow(foam_block.get_left() + LEFT * 0.3 + DOWN * 0.6,
                                foam_block.get_right() + RIGHT * 0.3 + DOWN * 0.6,
                                color=GRAY, buff=0.05)
        path_label = Text("longer, slower path", font_size=22, color=WHITE).next_to(zigzag, UP, buff=0.5)

        insight_line = Text("Slow down every path heat can travel", font_size=30, color=ManimColor("#FFD166")).shift(UP * 1.0)
        sub_line = Text("conduction · radiation · fewer particles", font_size=22, color=WHITE).next_to(insight_line, DOWN, buff=0.3)
        icons = VGroup(
            Circle(radius=0.3, color=ManimColor("#4FC3F7")),
            Square(side_length=0.55, color=ManimColor("#C0C0C0")),
            Triangle(color=ManimColor("#B08968")).scale(0.5),
        ).arrange(RIGHT, buff=1.0).shift(DOWN * 1.0)

        thermo_final = get_svg("thermometer", height=1.0).next_to(cup_body, LEFT, buff=0.6)
        temp_tracker = ValueTracker(95.0)
        temp_number = DecimalNumber(95.0, num_decimal_places=0, unit="°C", color=ManimColor("#FFD166"), font_size=28)
        temp_number.add_updater(lambda d: d.set_value(temp_tracker.get_value()))
        temp_number.next_to(thermo_final, UP, buff=0.15)
        clock_label = Text("hours later", font_size=24, color=WHITE).next_to(temp_number, UP, buff=0.1)

        final_line = Text("Science keeps your drink warm!", font_size=30, color=ManimColor("#FFD166")).shift(RIGHT * 1.0)

        self.add(background, divider)
        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Imagine you have a cup of hot chocolate. How do you keep it warm for as long as possible?") as tracker:
            sub = self.show_subtitle("Imagine you have a cup of hot chocolate. How do you keep it warm for as long as possible?")
            self.play(FadeIn(title, shift=UP * 0.3), rate_func=smooth, run_time=1.0)
            self.play(FadeIn(cup_group, shift=DOWN * 0.8), rate_func=smooth, run_time=1.4)
            self.play(GrowArrow(grav_arrow), FadeIn(grav_label), rate_func=smooth, run_time=0.8)
            self.play(FadeIn(thermo, shift=RIGHT * 0.2), rate_func=smooth, run_time=1.2)
            self.play(FadeIn(temp_start, shift=RIGHT * 0.2), rate_func=smooth, run_time=0.8)
            self.wait(max(0.1, tracker.duration - 5.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Six hours later, still eighty eight degrees. Where did the heat go?") as tracker:
            sub = self.show_subtitle("Six hours later, still eighty eight degrees. Where did the heat go?")
            self.play(FadeOut(grav_arrow, shift=UP * 0.2), FadeOut(grav_label, shift=UP * 0.2),
                      FadeOut(thermo, shift=RIGHT * 0.4), FadeOut(temp_start, shift=RIGHT * 0.4),
                      rate_func=rush_into, run_time=0.7)
            self.play(FadeIn(question_text, shift=UP * 0.4), rate_func=smooth, run_time=1.0)
            self.play(Create(qcircle), rate_func=linear, run_time=1.0)
            self.play(FadeIn(qmark, scale=0.6), FadeIn(heat_q, shift=UP * 0.2), rate_func=smooth, run_time=0.9)
            self.play(AnimationGroup(*[GrowArrow(a) for a in leak_arrows], lag_ratio=0.2),
                      rate_func=smooth, run_time=1.2)
            self.wait(max(0.1, tracker.duration - 5.3))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Let's start with double walls. A double-walled cup has a space between its walls. This space is often filled with air or even a vacuum.") as tracker:
            sub = self.show_subtitle("A double-walled cup has a space between its walls, filled with air or a vacuum.")
            self.play(FadeOut(qmark, shift=UP * 0.3), FadeOut(qcircle, shift=UP * 0.3),
                      FadeOut(question_text, shift=UP * 0.3), FadeOut(heat_q, shift=DOWN * 0.3),
                      FadeOut(leak_arrows, shift=RIGHT * 0.4), rate_func=rush_into, run_time=0.8)
            self.play(FadeIn(gap_region), rate_func=smooth, run_time=1.0)
            self.play(Create(inner_wall), rate_func=smooth, run_time=1.2)
            self.play(GrowArrow(wall_pointer), FadeIn(wall_label, shift=LEFT * 0.2),
                      rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 4.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Fewer particles are present to transfer energy, which means less heat escapes.") as tracker:
            sub = self.show_subtitle("Fewer particles means less energy transfer, so less heat escapes.")
            self.play(FadeOut(wall_pointer, shift=RIGHT * 0.3), FadeOut(wall_label, shift=RIGHT * 0.3),
                      rate_func=rush_into, run_time=0.5)
            self.play(AnimationGroup(*[FadeIn(d, scale=0.4) for d in gap_dots], lag_ratio=0.15),
                      rate_func=smooth, run_time=1.3)
            self.play(gap_dots.animate.shift(UP * 0.08 + RIGHT * 0.06), rate_func=there_and_back, run_time=0.8)
            self.play(AnimationGroup(*[FadeOut(d, scale=0.2) for d in gap_dots], lag_ratio=0.15),
                      rate_func=rush_into, run_time=1.2)
            self.play(GrowArrow(cond_arrow), rate_func=smooth, run_time=0.8)
            self.play(Create(block_cross), cond_arrow.animate.set_opacity(0.25), rate_func=smooth, run_time=0.8)
            self.play(FadeIn(vacuum_label, shift=UP * 0.2), rate_func=smooth, run_time=0.8)
            self.wait(max(0.1, tracker.duration - 6.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Next, think about shiny or light-colored cups. These surfaces reflect light.") as tracker:
            sub = self.show_subtitle("Shiny or light-colored surfaces reflect light instead of absorbing it.")
            self.play(FadeOut(cond_arrow, shift=LEFT * 0.3), FadeOut(block_cross, shift=LEFT * 0.3),
                      FadeOut(vacuum_label, shift=DOWN * 0.3), rate_func=rush_into, run_time=0.6)
            self.play(DrawBorderThenFill(silver_layer), rate_func=smooth, run_time=1.3)
            self.play(GrowArrow(mirror_pointer), FadeIn(mirror_label, shift=LEFT * 0.2),
                      rate_func=smooth, run_time=1.0)
            self.play(FadeIn(sweep), rate_func=smooth, run_time=0.4)
            self.play(sweep.animate.shift(DOWN * 2.8), rate_func=smooth, run_time=1.2)
            self.play(FadeOut(sweep), rate_func=rush_into, run_time=0.4)
            self.wait(max(0.1, tracker.duration - 5.3))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="When light is reflected, it doesn't get absorbed and turned into heat. So, your drink stays warm longer.") as tracker:
            sub = self.show_subtitle("Reflected light is not absorbed as heat, so your drink stays warm longer.")
            self.play(FadeOut(mirror_pointer, shift=RIGHT * 0.3), FadeOut(mirror_label, shift=RIGHT * 0.3),
                      rate_func=rush_into, run_time=0.5)
            self.play(GrowArrow(incoming_rays[1]), Create(normal_line), rate_func=smooth, run_time=0.9)
            self.play(FadeIn(photon), rate_func=smooth, run_time=0.3)
            self.play(MoveAlongPath(photon, v_path), GrowArrow(reflected_rays[1]),
                      rate_func=smooth, run_time=1.2)
            self.play(AnimationGroup(GrowArrow(incoming_rays[0]), GrowArrow(reflected_rays[0]),
                                     GrowArrow(incoming_rays[2]), GrowArrow(reflected_rays[2]),
                                     lag_ratio=0.2), rate_func=smooth, run_time=1.4)
            self.play(FadeIn(theta_tex, shift=UP * 0.2), FadeOut(photon), rate_func=smooth, run_time=0.8)
            self.play(Indicate(theta_tex, color=ManimColor("#FFD166")), run_time=0.8)
            self.wait(max(0.1, tracker.duration - 6.3))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Now, consider porous materials. These have tiny air pockets.") as tracker:
            sub = self.show_subtitle("Porous materials, like foam, contain tiny trapped air pockets.")
            self.play(FadeOut(incoming_rays, shift=LEFT * 0.3), FadeOut(reflected_rays, shift=RIGHT * 0.3),
                      FadeOut(normal_line), FadeOut(theta_tex, shift=UP * 0.3),
                      rate_func=rush_into, run_time=0.7)
            self.play(Create(magnifier), Create(connector_lines), rate_func=smooth, run_time=1.2)
            self.play(FadeIn(foam_block), rate_func=smooth, run_time=0.8)
            self.play(AnimationGroup(*[GrowFromCenter(p) for p in pores], lag_ratio=0.12),
                      rate_func=smooth, run_time=1.6)
            self.play(FadeIn(foam_label, shift=UP * 0.2), rate_func=smooth, run_time=0.7)
            self.wait(max(0.1, tracker.duration - 5.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Air is a poor conductor of heat, so less energy is transferred. This keeps your drink at the right temperature.") as tracker:
            sub = self.show_subtitle("Air conducts heat poorly, so energy takes a long, slow path through the foam.")
            self.play(AnimationGroup(*[Indicate(p, color=ManimColor("#4FC3F7"), scale_factor=1.3) for p in pores],
                                     lag_ratio=0.12), rate_func=smooth, run_time=1.6)
            self.play(Create(zigzag), FadeIn(heat_dot), rate_func=smooth, run_time=0.8)
            self.play(MoveAlongPath(heat_dot, zigzag), GrowArrow(straight_arrow),
                      rate_func=linear, run_time=2.2)
            self.play(FadeIn(path_label, shift=UP * 0.2), rate_func=smooth, run_time=0.8)
            self.wait(max(0.1, tracker.duration - 5.8))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="The secret is in slowing down how heat moves.") as tracker:
            sub = self.show_subtitle("The secret is slowing down every way that heat can move.")
            self.play(FadeOut(Group(magnifier, connector_lines, foam_block, pores, foam_label,
                                     zigzag, heat_dot, path_label, straight_arrow), shift=RIGHT * 0.5),
                      cup_group.animate.set_opacity(0.35),
                      inner_wall.animate.set_opacity(0.25), silver_layer.animate.set_opacity(0.25),
                      gap_region.animate.set_opacity(0.25),
                      rate_func=rush_into, run_time=1.0)
            self.play(FadeIn(insight_line, shift=UP * 0.3), rate_func=smooth, run_time=1.0)
            self.play(FadeIn(sub_line, shift=UP * 0.2), rate_func=smooth, run_time=0.8)
            self.play(Circumscribe(VGroup(insight_line, sub_line), color=ManimColor("#FFD166"), buff=0.3),
                      run_time=1.2)
            self.play(FadeIn(icons, shift=UP * 0.3), rate_func=smooth, run_time=0.9)
            self.wait(max(0.1, tracker.duration - 5.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="By using these features, we can keep our drinks hot or cold for longer.") as tracker:
            sub = self.show_subtitle("Together these features keep drinks hot or cold for hours.")
            self.play(FadeOut(VGroup(insight_line, sub_line, icons), shift=LEFT * 0.5),
                      cup_group.animate.set_opacity(1.0), rate_func=rush_into, run_time=0.9)
            self.play(DrawBorderThenFill(thermo_final), FadeIn(clock_label, shift=UP * 0.2),
                      rate_func=smooth, run_time=1.2)
            self.play(FadeIn(temp_number), run_time=0.4, rate_func=smooth)
            self.play(temp_tracker.animate.set_value(88.0), rate_func=smooth, run_time=2.0)
            self.play(Flash(thermo_final, color=ManimColor("#FFD166"), line_length=0.3, num_lines=12),
                      run_time=0.8)
            self.wait(max(0.1, tracker.duration - 5.3))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So next time you sip your hot chocolate, remember the science keeping it warm!") as tracker:
            sub = self.show_subtitle("Next time you sip your hot chocolate, remember the science keeping it warm!")
            self.remove(temp_number)
            self.play(FadeOut(VGroup(thermo_final, clock_label), shift=RIGHT * 0.5),
                      FadeOut(VGroup(inner_wall, gap_region, silver_layer)),
                      rate_func=rush_into, run_time=0.9)
            self.play(cup_group.animate.move_to(LEFT * 3.2 + DOWN * 0.2), rate_func=smooth, run_time=1.2)
            self.play(FadeIn(final_line, shift=UP * 0.3), rate_func=smooth, run_time=1.0)
            self.play(steam.animate.shift(UP * 0.4), rate_func=there_and_back, run_time=1.4)
            self.wait(max(0.1, tracker.duration - 5.0))
            self.play(FadeOut(VGroup(cup_group, final_line, title, divider), shift=DOWN * 0.3),
                      rate_func=smooth, run_time=1.2)
            self.play(FadeOut(sub), run_time=0.4)