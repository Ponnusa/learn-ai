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




class CupDesignChallenge(VoiceoverScene):
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

        # ═══ SETUP BLOCK: define every object used later ═══
        background = Rectangle(width=14.3, height=8.2, fill_color=ManimColor("#0D1117"),
                                fill_opacity=1, stroke_width=0)

        title = Text("Cup Design Challenge", font_size=36, color=WHITE).to_edge(UP, buff=0.4)

        cup_body = RoundedRectangle(width=1.4, height=1.8, corner_radius=0.15,
                                     color=WHITE, fill_color=BLUE_E, fill_opacity=0.25,
                                     stroke_width=3).move_to(LEFT * 2.5)
        cup = VGroup(cup_body)

        thermo1 = get_svg("thermometer", height=0.8).next_to(cup, RIGHT, buff=0.4)
        temp = DecimalNumber(95, unit="^\\circ C", num_decimal_places=0,
                              color=YELLOW).next_to(thermo1, UP, buff=0.2)

        question = Text("How do we keep it hot longer?", font_size=26,
                         color=WHITE).next_to(title, DOWN, buff=0.5)

        cond_arrow = Arrow(cup_body.get_right(), cup_body.get_right() + RIGHT * 1.2, color=ORANGE, buff=0)
        conv_arrow = Arrow(cup_body.get_top(), cup_body.get_top() + UP * 1.2, color=ORANGE, buff=0)
        rad_arrow = Arrow(cup_body.get_left(), cup_body.get_left() + LEFT * 1.2, color=ORANGE, buff=0)
        heat_arrows = VGroup(cond_arrow, conv_arrow, rad_arrow)

        heat_labels = VGroup(
            Text("Conduction", font_size=18, color=ORANGE).next_to(cond_arrow, RIGHT, buff=0.1),
            Text("Convection", font_size=18, color=ORANGE).next_to(conv_arrow, UP, buff=0.1),
            Text("Radiation", font_size=18, color=ORANGE).next_to(rad_arrow, LEFT, buff=0.1),
        )

        loss_eq = MathTex("Q = mc\\Delta T", color=WHITE, font_size=34).next_to(cup, DOWN, buff=0.6)

        outer_wall = RoundedRectangle(width=1.9, height=2.3, corner_radius=0.2,
                                       color=GRAY_B, fill_opacity=0.05,
                                       stroke_width=3).move_to(cup_body.get_center())
        vacuum_group = VGroup(*[
            Dot(point=cup_body.get_center() + np.array([np.cos(a), np.sin(a), 0]) * 0.85,
                radius=0.03, color=GRAY_B)
            for a in np.linspace(0, TAU, 10, endpoint=False)
        ])
        lid_seal = Rectangle(width=1.5, height=0.15, color=GRAY_B,
                              fill_opacity=0.6).next_to(cup_body, UP, buff=-0.05)
        sleeve = RoundedRectangle(width=1.6, height=0.8, corner_radius=0.1, color=GOLD,
                                   fill_opacity=0.4, stroke_width=2).move_to(RIGHT * 3 + DOWN * 2)

        callouts = VGroup(
            Text("Reflective layer", font_size=16, color=WHITE).move_to(LEFT * 4.3 + UP * 1.0),
            Text("Air pockets", font_size=16, color=WHITE).move_to(LEFT * 4.3 + UP * 0.3),
            Text("Insulating sleeve", font_size=16, color=WHITE).move_to(LEFT * 4.3 + DOWN * 0.4),
        )

        # --- Slope test rig geometry (kept consistent with where the cup lands) ---
        _cup_landing_pos = LEFT * 2.5 + RIGHT * 3.9 + UP * 1.2
        ramp_p1 = _cup_landing_pos + LEFT * 3 + DOWN * 1.3
        ramp_p2 = _cup_landing_pos + RIGHT * 3 + UP * 0.8
        ramp = Line(ramp_p1, ramp_p2, color=GRAY_B, stroke_width=6)
        _slope_vec = ramp_p2 - ramp_p1
        _slope_dir = _slope_vec / np.linalg.norm(_slope_vec)
        _normal_dir = np.array([-_slope_dir[1], _slope_dir[0], 0.0])
        if _normal_dir[1] < 0:
            _normal_dir = -_normal_dir

        trial_counter = Text("Trial 1", font_size=24, color=WHITE).to_corner(UR, buff=0.5)

        _cup_test_pos = _cup_landing_pos + _normal_dir * 0.5
        gravity = Arrow(_cup_test_pos, _cup_test_pos + DOWN * 1.0, color=RED, buff=0)
        normal = Arrow(_cup_test_pos, _cup_test_pos + _normal_dir * 1.0, color=BLUE, buff=0)
        mg_label = MathTex("mg", color=RED, font_size=28).next_to(gravity, DOWN, buff=0.1)
        n_label = MathTex("N", color=BLUE, font_size=28).next_to(normal, UP, buff=0.1)

        thermo2 = get_svg("thermometer", height=0.7).move_to(RIGHT * 5.2 + DOWN * 1.0)
        temp2 = DecimalNumber(70, unit="^\\circ C", num_decimal_places=0,
                               color=YELLOW).next_to(thermo2, UP, buff=0.2)

        plain_cup = RoundedRectangle(width=1.2, height=1.6, corner_radius=0.12, color=WHITE,
                                      fill_opacity=0.2, stroke_width=3).move_to(LEFT * 3.5 + DOWN * 0.5)
        plain_tag = Text("Plain cup", font_size=18, color=WHITE).next_to(plain_cup, UP, buff=0.2)
        insulated_tag = Text("Insulated cup", font_size=18, color=GOLD).move_to(RIGHT * 1.0 + UP * 2.0)

        thermo3 = get_svg("thermometer", height=0.6).next_to(plain_cup, RIGHT, buff=0.3)
        d_plain = DecimalNumber(55, unit="^\\circ C", num_decimal_places=0,
                                 color=RED).next_to(thermo3, UP, buff=0.2)

        thermo4 = get_svg("thermometer", height=0.6).move_to(RIGHT * 3.5 + DOWN * 0.5)
        d_new = DecimalNumber(88, unit="^\\circ C", num_decimal_places=0,
                               color=YELLOW).next_to(thermo4, UP, buff=0.2)

        banner = VGroup(
            Rectangle(width=6, height=1.0, color=GOLD, fill_opacity=0.15, stroke_width=2),
            Text("Insulation Wins!", font_size=28, color=GOLD)
        ).arrange(ORIGIN).move_to(UP * 2.6)
        banner.set_opacity(0)

        thermo5 = get_svg("thermometer", height=0.7).move_to(RIGHT * 1.3 + UP * 0.2)
        d_final = DecimalNumber(82, unit="^\\circ C", num_decimal_places=0,
                                 color=YELLOW).next_to(thermo5, UP, buff=0.2)

        steam = VGroup(*[
            Line(ORIGIN, UP * 0.4, color=GRAY_B, stroke_width=2).shift(
                RIGHT * (-0.3 + 0.3 * i) + UP * 0.6)
            for i in range(3)
        ])

        closing_line = Text("Still hot. That's engineering.", font_size=26,
                             color=WHITE).move_to(DOWN * 2.2)

        self.add(background)
        self.play(FadeOut(banner))

        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Imagine you have a cup of hot chocolate. How can you keep it hot for as long as possible?") as tracker:
            sub = self.show_subtitle("Imagine you have a cup of hot chocolate. How can you keep it hot for as long as possible?")
            self.play(FadeIn(title, shift=DOWN * 0.4), rate_func=smooth, run_time=1.0)
            self.play(DrawBorderThenFill(cup), rate_func=smooth, run_time=1.6)
            self.play(FadeIn(thermo1, shift=LEFT * 0.5), FadeIn(temp, shift=UP * 0.3),
                      rate_func=smooth, run_time=1.2)
            self.play(FadeIn(question, shift=UP * 0.2), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 5.2))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Energy likes to move from warm places to cool places. So, your hot chocolate loses heat to the cooler air around it.") as tracker:
            sub = self.show_subtitle("Energy likes to move from warm places to cool places. So, your hot chocolate loses heat to the cooler air around it.")
            self.play(FadeOut(question, shift=DOWN * 0.4), rate_func=rush_into, run_time=0.6)
            self.play(AnimationGroup(GrowArrow(cond_arrow), GrowArrow(conv_arrow),
                                     GrowArrow(rad_arrow), lag_ratio=0.25),
                      rate_func=smooth, run_time=2.0)
            self.play(AnimationGroup(*[FadeIn(l, shift=UP * 0.15) for l in heat_labels],
                                     lag_ratio=0.25), rate_func=smooth, run_time=1.4)
            self.play(FadeIn(loss_eq, shift=UP * 0.2), temp.animate.set_value(62),
                      rate_func=smooth, run_time=2.0)
            self.play(Indicate(loss_eq, color=YELLOW), run_time=0.6)
            self.wait(max(0.1, tracker.duration - 6.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="But what if we could slow that down? We can use materials that reflect light or have air pockets. These features act like a cozy blanket for your drink.") as tracker:
            sub = self.show_subtitle("But what if we could slow that down? We can use materials that reflect light or have air pockets. These features act like a cozy blanket for your drink.")
            self.play(FadeOut(loss_eq, shift=DOWN * 0.4), FadeOut(heat_labels, shift=DOWN * 0.3),
                      rate_func=rush_into, run_time=0.7)
            self.play(AnimationGroup(DrawBorderThenFill(outer_wall),
                                     FadeIn(vacuum_group, scale=1.1),
                                     FadeIn(lid_seal, shift=DOWN * 0.4),
                                     sleeve.animate.move_to(cup_body.get_center()),
                                     lag_ratio=0.25),
                      rate_func=smooth, run_time=3.0)
            self.play(AnimationGroup(*[FadeIn(c, shift=LEFT * 0.25) for c in callouts],
                                     lag_ratio=0.25), rate_func=smooth, run_time=2.0)
            self.play(cond_arrow.animate.scale(0.45, about_point=cond_arrow.get_start()).set_color(YELLOW),
                      conv_arrow.animate.scale(0.45, about_point=conv_arrow.get_start()).set_color(YELLOW),
                      rad_arrow.animate.scale(0.45, about_point=rad_arrow.get_start()).set_color(YELLOW),
                      rate_func=smooth, run_time=1.4)
            self.wait(max(0.1, tracker.duration - 7.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="We build our cup, test it, and see how well it works. Then, we make changes to improve it.") as tracker:
            sub = self.show_subtitle("We build our cup, test it, and see how well it works. Then, we make changes to improve it.")
            self.play(FadeOut(outer_wall, vacuum_group, sleeve, callouts, heat_arrows,
                              thermo1, temp, shift=UP * 0.3),
                      rate_func=rush_into, run_time=0.8)
            self.play(Create(ramp), FadeIn(trial_counter, shift=DOWN * 0.2),
                      rate_func=smooth, run_time=0.9)
            self.play(cup.animate.shift(RIGHT * 3.9 + UP * 1.2),
                      lid_seal.animate.shift(RIGHT * 3.9 + UP * 1.2),
                      rate_func=smooth, run_time=0.9)
            self.play(AnimationGroup(GrowArrow(gravity), GrowArrow(normal), lag_ratio=0.25),
                      FadeIn(mg_label), FadeIn(n_label), rate_func=smooth, run_time=1.0)
            self.play(cup.animate.shift(LEFT * 4.4 + DOWN * 1.3),
                      lid_seal.animate.shift(LEFT * 4.4 + DOWN * 1.3),
                      gravity.animate.shift(LEFT * 4.4 + DOWN * 1.3),
                      normal.animate.shift(LEFT * 4.4 + DOWN * 1.3),
                      mg_label.animate.shift(LEFT * 4.4 + DOWN * 1.3),
                      n_label.animate.shift(LEFT * 4.4 + DOWN * 1.3),
                      FadeIn(thermo2), FadeIn(temp2),
                      rate_func=smooth, run_time=1.8)
            self.play(temp2.animate.set_value(84), Indicate(trial_counter, scale_factor=1.2, color=GREEN),
                      rate_func=smooth, run_time=1.2)
            self.wait(max(0.1, tracker.duration - 6.8))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="The better our design, the longer our drink stays hot.") as tracker:
            sub = self.show_subtitle("The better our design, the longer our drink stays hot.")
            self.play(FadeOut(ramp, gravity, normal, mg_label, n_label, trial_counter,
                              thermo2, temp2, shift=DOWN * 0.4),
                      rate_func=rush_into, run_time=0.8)
            self.play(cup.animate.shift(RIGHT * 5.0 + UP * 0.7),
                      lid_seal.animate.shift(RIGHT * 5.0 + UP * 0.7),
                      rate_func=smooth, run_time=1.0)
            insulated_tag.move_to(RIGHT * 1.0 + UP * 2.0)
            self.play(FadeIn(plain_cup), FadeIn(plain_tag), FadeIn(insulated_tag),
                      FadeIn(thermo3), FadeIn(d_plain), FadeIn(thermo4), FadeIn(d_new),
                      rate_func=smooth, run_time=1.2)
            self.play(d_new.animate.set_value(79).set_color(GOLD),
                      plain_cup.animate.set_opacity(0.3),
                      rate_func=smooth, run_time=1.5)
            self.play(Flash(d_new, color=GOLD, line_length=0.4, num_lines=16), run_time=0.8)
            self.play(FadeIn(banner, shift=UP * 0.2), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 6.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So next time you sip your hot chocolate, remember, it's all about keeping that energy right where you want it!") as tracker:
            sub = self.show_subtitle("So next time you sip your hot chocolate, remember, it's all about keeping that energy right where you want it!")
            self.play(FadeOut(plain_cup, plain_tag, thermo3, d_plain, thermo4, d_new,
                              insulated_tag, banner, lid_seal, shift=DOWN * 0.6),
                      rate_func=rush_into, run_time=1.0)
            self.play(cup.animate.move_to(DOWN * 0.2).scale(1.1),
                      FadeIn(thermo5), FadeIn(d_final),
                      rate_func=smooth, run_time=1.4)
            self.play(AnimationGroup(*[Create(s) for s in steam], lag_ratio=0.3),
                      rate_func=smooth, run_time=1.5)
            self.play(FadeIn(closing_line, shift=UP * 0.2), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 6.2))
            self.play(FadeOut(cup, thermo5, d_final, steam, closing_line, title, shift=DOWN * 0.4),
                      rate_func=smooth, run_time=1.3)
            self.play(FadeOut(sub), run_time=0.4)