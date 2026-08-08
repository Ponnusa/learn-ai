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




class HotCupInWaterBath(VoiceoverScene):
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
        self.camera.background_color = ManimColor("#0E1116")

        # ═══ SETUP BLOCK: define all objects used below ═══
        HOT = ORANGE
        COOL = BLUE
        EQ = GREEN

        background = Rectangle(width=15, height=9, fill_color="#0E1116",
                                fill_opacity=1, stroke_width=0)

        bath_glass = RoundedRectangle(width=5.2, height=3.4, corner_radius=0.15,
                                       stroke_color=WHITE, stroke_width=3,
                                       fill_opacity=0).move_to(DOWN * 1.3)

        water = RoundedRectangle(width=5.0, height=2.6, corner_radius=0.1,
                                  fill_color=COOL, fill_opacity=0.35,
                                  stroke_width=0).move_to(bath_glass.get_center() + DOWN * 0.3)

        _wl_start = water.get_top() + LEFT * 2.4
        _wl_end = water.get_top() + RIGHT * 2.4
        if np.linalg.norm(_wl_end - _wl_start) > 0.01:
            waterline = Line(_wl_start, _wl_end, color=COOL, stroke_width=2)
        else:
            waterline = VGroup()

        CUP_START = UP * 2.0
        CUP_END = bath_glass.get_center() + UP * 0.3

        cup = RoundedRectangle(width=1.1, height=1.0, corner_radius=0.08,
                                fill_color=HOT, fill_opacity=0.85,
                                stroke_color=WHITE, stroke_width=2).move_to(CUP_START)

        cup_path = Line(CUP_START, CUP_END)

        therm_cup = get_svg("thermometer", height=0.55).next_to(cup, RIGHT, buff=0.15)
        therm_bath = get_svg("thermometer", height=0.55).next_to(bath_glass, LEFT, buff=0.15)

        labels = VGroup(
            Text("Hot Chocolate", font_size=20, color=HOT).next_to(cup, UP, buff=0.15),
            Text("Water Bath", font_size=20, color=COOL).next_to(bath_glass, DOWN, buff=0.15),
        )

        t_cup = DecimalNumber(85, num_decimal_places=1, color=HOT).scale(0.6).next_to(therm_cup, UP, buff=0.1)
        t_bath = DecimalNumber(20, num_decimal_places=1, color=COOL).scale(0.6).next_to(therm_bath, UP, buff=0.1)
        readouts = VGroup(t_cup, t_bath)

        q = Text("Does it stay hot forever?", font_size=32, color=WHITE).to_edge(UP, buff=0.6)
        sub_q = Text("...or does something else happen?", font_size=22, color=GRAY_B).next_to(q, DOWN, buff=0.2)
        _qu_start = q.get_left() + DOWN * 0.15
        _qu_end = q.get_right() + DOWN * 0.15
        if np.linalg.norm(_qu_end - _qu_start) > 0.01:
            q_underline = Line(_qu_start, _qu_end, color=EQ, stroke_width=2)
        else:
            q_underline = VGroup()

        arr_hot = Arrow(cup.get_bottom(), bath_glass.get_top() + LEFT * 0.4,
                         color=HOT, buff=0.1, stroke_width=6)
        arr_cool = Arrow(bath_glass.get_top() + RIGHT * 0.4, cup.get_bottom(),
                          color=COOL, buff=0.1, stroke_width=4)
        lab_hot = Text("heat out", font_size=18, color=HOT).next_to(arr_hot, LEFT, buff=0.1)
        lab_cool = Text("heat in", font_size=18, color=COOL).next_to(arr_cool, RIGHT, buff=0.1)

        grav_group = VGroup(
            Arrow(cup.get_top() + UP * 0.1, cup.get_top() + UP * 0.5,
                  color=HOT, stroke_width=3, buff=0),
            Text("heat", font_size=14, color=HOT).next_to(cup, UP, buff=0.55),
        )

        q1 = Arrow(CUP_END + LEFT * 0.5, CUP_END + LEFT * 0.5 + DOWN * 0.8, color=HOT, stroke_width=5)
        q2 = Arrow(CUP_END, CUP_END + DOWN * 0.9, color=HOT, stroke_width=5)
        q3 = Arrow(CUP_END + RIGHT * 0.5, CUP_END + RIGHT * 0.5 + DOWN * 0.8, color=HOT, stroke_width=5)
        heat_arrows = VGroup(q1, q2, q3)
        q_label = Text("Heat Transfer", font_size=20, color=HOT).move_to(UP * 1.0)

        col_cup = Rectangle(width=0.3, height=1.4, fill_color=HOT, fill_opacity=0.7,
                             stroke_width=0).next_to(therm_cup, DOWN, buff=0.3)
        col_bath = Rectangle(width=0.3, height=0.5, fill_color=COOL, fill_opacity=0.7,
                              stroke_width=0).next_to(therm_bath, DOWN, buff=0.3)

        mid_note = Text("Both temperatures move toward the middle", font_size=20,
                         color=WHITE).to_edge(DOWN, buff=1.1)

        _gl1_start = arr_hot.get_start() + UP * 0.3
        _gl1_end = arr_hot.get_end() + UP * 0.3
        _gl2_start = arr_cool.get_start() + UP * 0.3
        _gl2_end = arr_cool.get_end() + UP * 0.3
        ghost_lines = VGroup()
        if np.linalg.norm(_gl1_end - _gl1_start) > 0.01:
            ghost_lines.add(DashedLine(_gl1_start, _gl1_end, color=GRAY_B, stroke_width=1.5))
        if np.linalg.norm(_gl2_end - _gl2_start) > 0.01:
            ghost_lines.add(DashedLine(_gl2_start, _gl2_end, color=GRAY_B, stroke_width=1.5))

        brace_hot = Brace(arr_hot, direction=UP, color=HOT)
        brace_cool = Brace(arr_cool, direction=DOWN, color=COOL)
        lab_dT_hot = MathTex(r"\Delta T_{hot}", color=HOT).scale(0.7).next_to(brace_hot, UP, buff=0.1)
        lab_dT_cool = MathTex(r"\Delta T_{cool}", color=COOL).scale(0.7).next_to(brace_cool, DOWN, buff=0.1)

        insight_title = Text("Energy Transfer", font_size=28, color=EQ)
        insight_desc = Text("Heat flows from hot to cold", font_size=20,
                             color=WHITE).next_to(insight_title, DOWN, buff=0.2)
        insight = VGroup(insight_title, insight_desc).move_to(UP * 0.2)
        insight_box = SurroundingRectangle(insight, color=EQ, buff=0.2)

        result_lhs = MathTex(r"T_{eq} =", color=WHITE).scale(0.9)
        result_num = DecimalNumber(20, num_decimal_places=1, color=EQ).scale(0.9)
        result_unit = MathTex(r"^\circ C", color=WHITE).scale(0.9)
        result_num.next_to(result_lhs, RIGHT, buff=0.15)
        result_unit.next_to(result_num, RIGHT, buff=0.1)
        result = VGroup(result_lhs, result_num, result_unit).move_to(DOWN * 2.0)

        _eq_start = result.get_left() + LEFT * 0.3
        _eq_end = result.get_right() + RIGHT * 0.3
        if np.linalg.norm(_eq_end - _eq_start) > 0.01:
            eq_line = DashedLine(_eq_start, _eq_end, color=EQ, stroke_width=2)
        else:
            eq_line = VGroup()

        answer = Text("Equilibrium Reached!", font_size=30, color=EQ).move_to(DOWN * 2.0)
        closing = Text("It's all about sharing warmth!", font_size=26, color=WHITE).to_edge(DOWN, buff=1.0)
        # ═══ END SETUP BLOCK ═══

        self.add(background)
        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Imagine you have a cup of hot chocolate. Now, what happens if you put that cup in a cold water bath?") as tracker:
            sub = self.show_subtitle("Imagine you have a cup of hot chocolate. Now, what happens if you put that cup in a cold water bath?")
            self.play(FadeIn(bath_glass, shift=UP * 0.4), rate_func=smooth, run_time=1.2)
            self.play(DrawBorderThenFill(water), Create(waterline), rate_func=smooth, run_time=1.4)
            self.play(FadeIn(cup, shift=DOWN * 0.4), rate_func=rush_from, run_time=1.1)
            self.play(AnimationGroup(FadeIn(therm_cup, shift=RIGHT * 0.2),
                                     FadeIn(therm_bath, shift=LEFT * 0.2),
                                     lag_ratio=0.3), rate_func=smooth, run_time=1.4)
            self.play(FadeIn(labels, shift=UP * 0.2), FadeIn(readouts, shift=UP * 0.2),
                      rate_func=smooth, run_time=1.2)
            self.wait(max(0.1, tracker.duration - 6.8))
            self.play(FadeOut(sub), FadeOut(labels), run_time=0.4)

        with self.voiceover(text="Does the hot chocolate stay hot forever? Or does something else happen?") as tracker:
            sub = self.show_subtitle("Does the hot chocolate stay hot forever? Or does something else happen?")
            self.play(FadeIn(q, shift=DOWN * 0.3), rate_func=smooth, run_time=1.2)
            self.play(FadeIn(sub_q, shift=DOWN * 0.2), rate_func=smooth, run_time=1.0)
            self.play(Create(q_underline), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 3.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Let's explore this! When you place the cup in the water bath, the heat from the hot chocolate starts to move.") as tracker:
            sub = self.show_subtitle("Let's explore this! When you place the cup in the water bath, the heat from the hot chocolate starts to move.")
            self.play(
                FadeOut(q, shift=UP * 0.3), FadeOut(sub_q, shift=UP * 0.3),
                FadeOut(q_underline, shift=UP * 0.3),
                AnimationGroup(GrowArrow(arr_hot), GrowArrow(arr_cool), lag_ratio=0.25),
                rate_func=smooth, run_time=2.0)
            self.play(AnimationGroup(FadeIn(lab_hot, shift=UP * 0.2), FadeIn(lab_cool, shift=UP * 0.2),
                                     lag_ratio=0.25), rate_func=smooth, run_time=1.4)
            self.play(Indicate(arr_hot, color=HOT, scale_factor=1.15), run_time=1.0)
            self.wait(max(0.1, tracker.duration - 5.2))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="It travels through the cup wall into the cold water. This is because heat always moves from warmer places to cooler ones.") as tracker:
            sub = self.show_subtitle("It travels through the cup wall into the cold water. Heat always moves from warmer places to cooler ones.")
            self.play(FadeIn(grav_group), rate_func=smooth, run_time=0.6)
            moving_extras = VGroup(arr_hot, arr_cool, lab_hot, lab_cool, therm_cup, t_cup)
            self.play(MoveAlongPath(cup, cup_path),
                      grav_group.animate.shift(CUP_END - CUP_START),
                      moving_extras.animate.shift(CUP_END - CUP_START),
                      rate_func=smooth, run_time=2.4)
            self.play(FadeOut(grav_group, shift=DOWN * 0.2), rate_func=rush_into, run_time=0.6)
            self.play(AnimationGroup(GrowArrow(q1), GrowArrow(q2), GrowArrow(q3), lag_ratio=0.25),
                      rate_func=smooth, run_time=1.6)
            self.play(FadeIn(q_label, shift=UP * 0.2), rate_func=smooth, run_time=0.8)
            self.play(AnimationGroup(*[a.animate(rate_func=there_and_back).set_stroke(width=11)
                                       for a in heat_arrows], lag_ratio=0.15), run_time=1.2)
            self.wait(max(0.1, tracker.duration - 7.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="As time goes on, the temperature inside the cup drops, while the water bath gets a bit warmer.") as tracker:
            sub = self.show_subtitle("As time goes on, the temperature inside the cup drops, while the water bath gets a bit warmer.")
            col_cup.next_to(therm_cup, DOWN, buff=0.3)
            self.play(FadeIn(col_cup), FadeIn(col_bath), rate_func=smooth, run_time=0.8)
            self.play(t_cup.animate.set_value(34.2), t_bath.animate.set_value(34.2),
                      col_cup.animate.stretch_to_fit_height(0.9),
                      col_bath.animate.stretch_to_fit_height(0.9),
                      arr_hot.animate.scale(0.44, about_point=arr_hot.get_start()),
                      arr_cool.animate.scale(1.55, about_point=arr_cool.get_start()),
                      rate_func=smooth, run_time=4.5)
            self.play(FadeIn(mid_note, shift=UP * 0.2), rate_func=smooth, run_time=1.2)
            self.wait(max(0.1, tracker.duration - 7.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="The bigger the temperature difference, the faster the heat moves.") as tracker:
            sub = self.show_subtitle("The bigger the temperature difference, the faster the heat moves.")
            # Recompute brace/ghost_lines based on shifted arrow positions (arrows moved in scene 4)
            brace_hot = Brace(arr_hot, direction=UP, color=HOT)
            brace_cool = Brace(arr_cool, direction=DOWN, color=COOL)
            lab_dT_hot = MathTex(r"\Delta T_{hot}", color=HOT).scale(0.7).next_to(brace_hot, UP, buff=0.1)
            lab_dT_cool = MathTex(r"\Delta T_{cool}", color=COOL).scale(0.7).next_to(brace_cool, DOWN, buff=0.1)
            _gl1_start = arr_hot.get_start() + UP * 0.3
            _gl1_end = arr_hot.get_end() + UP * 0.3
            _gl2_start = arr_cool.get_start() + UP * 0.3
            _gl2_end = arr_cool.get_end() + UP * 0.3
            ghost_lines = VGroup()
            if np.linalg.norm(_gl1_end - _gl1_start) > 0.01:
                ghost_lines.add(DashedLine(_gl1_start, _gl1_end, color=GRAY_B, stroke_width=1.5))
            if np.linalg.norm(_gl2_end - _gl2_start) > 0.01:
                ghost_lines.add(DashedLine(_gl2_start, _gl2_end, color=GRAY_B, stroke_width=1.5))
            self.play(FadeOut(mid_note, shift=DOWN * 0.2), FadeIn(ghost_lines), rate_func=smooth, run_time=0.8)
            self.play(AnimationGroup(GrowFromCenter(brace_hot), FadeIn(lab_dT_hot, shift=RIGHT * 0.2),
                                     GrowFromCenter(brace_cool), FadeIn(lab_dT_cool, shift=LEFT * 0.2),
                                     lag_ratio=0.25), rate_func=smooth, run_time=2.6)
            self.play(Indicate(lab_dT_hot, color=HOT, scale_factor=1.25), run_time=0.8)
            self.play(Indicate(lab_dT_cool, color=COOL, scale_factor=1.25), run_time=0.8)
            self.wait(max(0.1, tracker.duration - 5.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="This is called energy transfer. It's like when you hold a cold drink, and your hand feels cold because heat moves from your hand to the drink.") as tracker:
            sub = self.show_subtitle("This is called energy transfer. Heat moves from your hand into a cold drink in the same way.")
            self.play(FadeIn(insight, shift=DOWN * 0.2), rate_func=smooth, run_time=2.0)
            self.play(Circumscribe(insight[0], color=EQ), run_time=1.6)
            self.play(Indicate(insight[0], color=EQ, scale_factor=1.4), run_time=1.2)
            self.play(Create(insight_box), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 6.2))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So, the hot chocolate doesn't stay hot forever. It shares its heat with the water until both are the same temperature.") as tracker:
            sub = self.show_subtitle("The hot chocolate shares its heat with the water until both are the same temperature.")
            self.play(FadeIn(result_lhs), FadeIn(result_unit), result_num.animate.set_value(34.2),
                      rate_func=smooth, run_time=2.0)
            self.play(Circumscribe(result, color=EQ, fade_out=False), run_time=1.4)
            self.play(AnimationGroup(cup.animate.set_fill(EQ, 0.5).set_stroke(EQ),
                                     water.animate.set_fill(EQ, 0.32), lag_ratio=0.2),
                      rate_func=smooth, run_time=1.6)
            self.play(Create(eq_line), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 6.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Next time you enjoy a hot drink, remember, it's all about sharing warmth with its surroundings!") as tracker:
            sub = self.show_subtitle("Next time you enjoy a hot drink, remember, it's all about sharing warmth with its surroundings!")
            self.play(FadeOut(VGroup(heat_arrows, q_label, arr_hot, arr_cool, lab_hot, lab_cool,
                                     brace_hot, brace_cool, lab_dT_hot, lab_dT_cool,
                                     insight, insight_box, ghost_lines, eq_line,
                                     col_cup, col_bath), shift=UP * 0.3),
                      rate_func=rush_into, run_time=1.4)
            self.play(ReplacementTransform(result.copy(), answer), FadeOut(result, shift=UP * 0.2),
                      rate_func=smooth, run_time=1.4)
            self.play(FadeIn(closing, shift=UP * 0.2), cup.animate.shift(DOWN * 0.08),
                      rate_func=smooth, run_time=1.4)
            self.wait(max(0.1, tracker.duration - 5.0))
            self.play(FadeOut(sub), run_time=0.4)

        self.play(FadeOut(Group(*self.mobjects), shift=DOWN * 0.3), rate_func=rush_into, run_time=1.8)