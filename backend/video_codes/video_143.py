from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.azure import AzureService
import numpy as np

import base64 as _b64_svg, os as _os

_SVG_DATA = {
    "thermometer": "PHN2ZyB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8Y2lyY2xlIGN4PSI1MCIgY3k9IjgwIiByPSIxMCIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyLjUiLz4KICA8cGF0aCBkPSJNIDQ0IDcwIEwgNDQgMjAgUSA0NCAxNSA1MCAxNSBRIDU2IDE1IDU2IDIwIEwgNTYgNzAiIHN0cm9rZT0id2hpdGUiIGZpbGw9Im5vbmUiIHN0cm9rZS13aWR0aD0iMi41Ii8+CiAgPGxpbmUgeDE9IjQ0IiB5MT0iNzAiIHgyPSI1NiIgeTI9IjcwIiBzdHJva2U9IndoaXRlIiBmaWxsPSJub25lIiBzdHJva2Utd2lkdGg9IjIuNSIvPgogIDxsaW5lIHgxPSI0NiIgeTE9IjQ1IiB4Mj0iNTQiIHkyPSI0NSIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyLjUiLz4KICA8bGluZSB4MT0iNDYiIHkxPSIzNSIgeDI9IjUyIiB5Mj0iMzUiIHN0cm9rZT0id2hpdGUiIGZpbGw9Im5vbmUiIHN0cm9rZS13aWR0aD0iMiIvPgogIDxsaW5lIHgxPSI0NiIgeTE9IjU1IiB4Mj0iNTIiIHkyPSI1NSIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyIi8+Cjwvc3ZnPg==",
    "balance_scale": "PHN2ZyB2aWV3Qm94PSIwIDAgMjAwIDEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiBzdHJva2U9IndoaXRlIiBmaWxsPSJub25lIiBzdHJva2Utd2lkdGg9IjIuNSI+CiAgPCEtLSBDZW50cmFsIHZlcnRpY2FsIHJvZCAtLT4KICA8bGluZSB4MT0iMTAwIiB5MT0iMjAiIHgyPSIxMDAiIHkyPSI3NSIvPgogIDwhLS0gQmFzZSAtLT4KICA8bGluZSB4MT0iODUiIHkxPSI3NSIgeDI9IjExNSIgeTI9Ijc1Ii8+CiAgPCEtLSBQaXZvdCBwb2ludCBjaXJjbGUgLS0+CiAgPGNpcmNsZSBjeD0iMTAwIiBjeT0iMjgiIHI9IjMiLz4KICA8IS0tIEhvcml6b250YWwgYmVhbSAtLT4KICA8bGluZSB4MT0iNDAiIHkxPSIyOCIgeDI9IjE2MCIgeTI9IjI4Ii8+CiAgPCEtLSBMZWZ0IHN0cmluZ3MgLS0+CiAgPGxpbmUgeDE9IjQwIiB5MT0iMjgiIHgyPSIyNSIgeTI9IjU1Ii8+CiAgPGxpbmUgeDE9IjQwIiB5MT0iMjgiIHgyPSI1NSIgeTI9IjU1Ii8+CiAgPCEtLSBMZWZ0IHBhbiAtLT4KICA8cGF0aCBkPSJNMjIsNTUgUTQwLDYyIDU4LDU1Ii8+CiAgPCEtLSBSaWdodCBzdHJpbmdzIC0tPgogIDxsaW5lIHgxPSIxNjAiIHkxPSIyOCIgeDI9IjE0NSIgeTI9IjU1Ii8+CiAgPGxpbmUgeDE9IjE2MCIgeTE9IjI4IiB4Mj0iMTc1IiB5Mj0iNTUiLz4KICA8IS0tIFJpZ2h0IHBhbiAtLT4KICA8cGF0aCBkPSJNMTQyLDU1IFExNjAsNjIgMTc4LDU1Ii8+Cjwvc3ZnPg=="
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



class LidKeepsDrinkHot(VoiceoverScene):
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

        # ═══ SETUP BLOCK: define all objects used across the video ═══
        HEAT = ORANGE
        COLD = BLUE
        LIDC = GRAY_B

        background = Rectangle(width=15, height=9, fill_color=ManimColor("#0D1117"),
                                fill_opacity=1, stroke_width=0)

        def make_cup(center, with_lid=False):
            body = RoundedRectangle(width=1.3, height=1.5, corner_radius=0.15,
                                     color=WHITE, stroke_width=3)
            body.move_to(center)
            liquid = Ellipse(width=1.05, height=0.28, color=HEAT, fill_opacity=1,
                              stroke_width=0).move_to(body.get_top() + DOWN * 0.18)
            cup = VGroup(body, liquid)
            lid = None
            if with_lid:
                lid = Ellipse(width=1.2, height=0.22, color=LIDC, fill_opacity=1,
                              stroke_width=2).move_to(body.get_top() + UP * 0.05)
            return cup, lid

        open_cup, _open_lid = make_cup(LEFT * 3.4 + DOWN * 0.4, with_lid=False)
        closed_cup, seated_lid = make_cup(RIGHT * 3.4 + DOWN * 0.4, with_lid=True)
        self.add(seated_lid)

        labels_1 = VGroup(
            Text("No Lid", font_size=22, color=WHITE).next_to(open_cup, DOWN, buff=0.3),
            Text("With Lid", font_size=22, color=WHITE).next_to(closed_cup, DOWN, buff=0.3),
        )
        title_1 = Text("Does a lid keep your drink hotter?", font_size=28, color=WHITE).to_edge(UP, buff=0.6)

        falling_lid = seated_lid.copy()
        self.add(falling_lid)

        gravity_arrow = Arrow(seated_lid.get_center(), seated_lid.get_center() + DOWN * 0.9,
                               color=YELLOW, buff=0)
        gravity_label = Text("gravity", font_size=20, color=YELLOW).next_to(gravity_arrow, RIGHT, buff=0.15)

        wisps = [
            ParametricFunction(lambda t, i=i: np.array([0.15 * np.sin(3 * t + i), t, 0]),
                                t_range=[0, 1.2], color=GRAY_B, stroke_width=2).move_to(
                open_cup.get_top() + UP * 0.3 + RIGHT * 0.15 * i)
            for i in range(3)
        ]
        escapees = [Dot(radius=0.05, color=GRAY_B).move_to(open_cup.get_top() + UP * 0.2 + RIGHT * 0.1 * i)
                    for i in range(-2, 3)]
        steam_caption = Text("Steam escapes!", font_size=22, color=GRAY_B).next_to(open_cup, UP, buff=1.6)

        zoom_panel = RoundedRectangle(width=5.6, height=3.4, corner_radius=0.2,
                                       color=WHITE, stroke_width=2).move_to(DOWN * 0.3)
        cone_lines = VGroup()
        _cs, _ce = zoom_panel.get_left(), open_cup.get_right()
        if np.linalg.norm(np.array(_ce) - np.array(_cs)) > 0.01:
            cone_lines.add(Line(_cs, _ce, color=WHITE, stroke_width=1.5))

        liquid_dots = [Dot(radius=0.07, color=HEAT).move_to(
            zoom_panel.get_center() + LEFT * 1.6 + DOWN * 0.3 * j + RIGHT * 0.3 * k)
            for j in range(2) for k in range(2)]
        gas_dots = [Dot(radius=0.06, color=GRAY_B).move_to(zoom_panel.get_center() + RIGHT * 1.5 + UP * 0.4 * j)
                    for j in range(-1, 2)]
        liquid_arrows = [Arrow(d.get_center(), d.get_center() + RIGHT * 0.25, buff=0, color=HEAT, stroke_width=2)
                         for d in liquid_dots]
        gas_arrows = [Arrow(d.get_center(), d.get_center() + RIGHT * 0.45, buff=0, color=GRAY_B, stroke_width=2)
                     for d in gas_dots]
        ke_formula = MathTex(r"KE = \tfrac{1}{2}mv^2", font_size=32, color=WHITE).next_to(zoom_panel, DOWN, buff=0.3)

        panel_group = VGroup(zoom_panel, cone_lines, *liquid_dots, *gas_dots,
                              *liquid_arrows, *gas_arrows, ke_formula)

        barrier_line = Line(LEFT * 2.2 + UP * 1.0, RIGHT * 2.2 + UP * 1.0, color=LIDC, stroke_width=4)
        vapor_arrows = VGroup(*[Arrow(ORIGIN, UP * 0.5, buff=0, color=GRAY_B, stroke_width=2).move_to(
            LEFT * 1.5 + RIGHT * 0.75 * i + DOWN * 0.3) for i in range(5)])
        vapor_dots = VGroup(*[Dot(radius=0.06, color=GRAY_B).move_to(LEFT * 1.5 + RIGHT * 0.75 * i + DOWN * 0.7)
                              for i in range(5)])
        condense_text = Text("Vapor condenses back!", font_size=22, color=WHITE).to_edge(DOWN, buff=1.0)

        vt_L = ValueTracker(0.1)
        vt_R = ValueTracker(0.1)
        merc_L = Rectangle(width=0.25, height=1.6, color=RED, fill_color=RED, fill_opacity=1, stroke_width=1)
        merc_L.add_updater(lambda m: m.stretch_to_fit_height(max(0.05, 1.6 * vt_L.get_value())).move_to(
            LEFT * 3.2 + DOWN * 1.0 + UP * (1.6 * vt_L.get_value()) / 2))
        merc_R = Rectangle(width=0.25, height=1.6, color=RED, fill_color=RED, fill_opacity=1, stroke_width=1)
        merc_R.add_updater(lambda m: m.stretch_to_fit_height(max(0.05, 1.6 * vt_R.get_value())).move_to(
            RIGHT * 3.2 + DOWN * 1.0 + UP * (1.6 * vt_R.get_value()) / 2))

        balance_scale = get_svg("balance_scale", height=1.6).move_to(DOWN * 0.5)
        thermo_L = get_svg("thermometer", height=1.8).move_to(LEFT * 3.2 + UP * 0.2)
        thermo_R = get_svg("thermometer", height=1.8).move_to(RIGHT * 3.2 + UP * 0.2)
        thermo_L_label = Text("No Lid", font_size=20, color=WHITE).next_to(thermo_L, DOWN, buff=0.2)
        thermo_R_label = Text("With Lid", font_size=20, color=WHITE).next_to(thermo_R, DOWN, buff=0.2)
        sixty_text = Text("Both start at 60°C", font_size=22, color=WHITE).to_edge(UP, buff=0.8)
        pivot_point = balance_scale.get_top()
        compare_group = VGroup(balance_scale, thermo_L, thermo_R, thermo_L_label, thermo_R_label)

        mech_cup, mech_lid = make_cup(ORIGIN + DOWN * 0.3, with_lid=True)
        mech_arrow_1 = Arrow(mech_cup.get_top() + LEFT * 1.5, mech_cup.get_top() + LEFT * 0.6,
                              color=YELLOW, buff=0)
        mech_text_1 = Text("less steam escapes", font_size=20, color=WHITE).next_to(mech_arrow_1, LEFT, buff=0.15)
        mech_arrow_2 = Arrow(mech_cup.get_top() + UP * 0.9, mech_cup.get_top() + UP * 0.15,
                              color=HEAT, buff=0)
        mech_text_2 = Text("heat trapped inside", font_size=20, color=WHITE).next_to(mech_arrow_2, UP, buff=0.15)
        mech_arrow_3 = Arrow(mech_cup.get_top() + RIGHT * 1.5, mech_cup.get_top() + RIGHT * 0.6,
                              color=COLD, buff=0)
        mech_text_3 = Text("slower cooling", font_size=20, color=WHITE).next_to(mech_arrow_3, RIGHT, buff=0.15)
        mech_group = VGroup(mech_arrow_1, mech_text_1, mech_arrow_2, mech_text_2, mech_arrow_3, mech_text_3)

        insight_main = Text("A lid slows heat loss and evaporation", font_size=30, color=WHITE).move_to(UP * 0.4)
        insight_sub = Text("keeping your drink hotter for longer", font_size=24, color=GRAY_B).next_to(
            insight_main, DOWN, buff=0.35)

        temp_L = ValueTracker(60.0)
        temp_R = ValueTracker(60.0)
        res_merc_L = Rectangle(width=0.25, height=1.6, color=RED, fill_color=RED, fill_opacity=1, stroke_width=1)
        res_merc_L.add_updater(lambda m: m.stretch_to_fit_height(
            max(0.05, 1.6 * (temp_L.get_value() / 100))).move_to(
            LEFT * 3.2 + DOWN * 1.0 + UP * (1.6 * (temp_L.get_value() / 100)) / 2))
        res_merc_R = Rectangle(width=0.25, height=1.6, color=RED, fill_color=RED, fill_opacity=1, stroke_width=1)
        res_merc_R.add_updater(lambda m: m.stretch_to_fit_height(
            max(0.05, 1.6 * (temp_R.get_value() / 100))).move_to(
            RIGHT * 3.2 + DOWN * 1.0 + UP * (1.6 * (temp_R.get_value() / 100)) / 2))
        num_L = DecimalNumber(60.0, num_decimal_places=0, unit="^{\\circ}C", font_size=22, color=WHITE)
        num_L.add_updater(lambda m: m.set_value(temp_L.get_value()))
        num_L.next_to(res_merc_L, UP, buff=0.6)
        num_R = DecimalNumber(60.0, num_decimal_places=0, unit="^{\\circ}C", font_size=22, color=WHITE)
        num_R.add_updater(lambda m: m.set_value(temp_R.get_value()))
        num_R.next_to(res_merc_R, UP, buff=0.6)

        res_thermo_L = get_svg("thermometer", height=1.8).move_to(LEFT * 3.2 + UP * 0.2)
        res_thermo_R = get_svg("thermometer", height=1.8).move_to(RIGHT * 3.2 + UP * 0.2)
        deg_R = num_R
        result_group = VGroup(res_thermo_L, res_thermo_R, num_L, num_R)
        result_caption = Text("The lid keeps it warmer!", font_size=22, color=WHITE).to_edge(DOWN, buff=1.0)

        final_cup, final_lid = make_cup(ORIGIN + DOWN * 0.3, with_lid=True)
        final_group = VGroup(final_cup, final_lid)
        closing_line = Text("A small lid makes a big difference!", font_size=26, color=WHITE).to_edge(UP, buff=1.0)

        self.add(background)
        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Imagine you have a steaming cup of hot chocolate. What happens if you put a lid on it?") as tracker:
            sub = self.show_subtitle("Imagine you have a steaming cup of hot chocolate. What happens if you put a lid on it?")
            self.play(DrawBorderThenFill(open_cup), run_time=1.6)
            self.play(DrawBorderThenFill(closed_cup), run_time=1.6)
            self.play(FadeIn(labels_1, shift=UP * 0.3), run_time=0.8)
            self.play(FadeIn(title_1, shift=DOWN * 0.25), rate_func=smooth, run_time=1.2)
            self.wait(max(0.1, tracker.duration - 6.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Does it stay hot longer?") as tracker:
            sub = self.show_subtitle("Does it stay hot longer?")
            self.remove(seated_lid)
            self.play(AnimationGroup(GrowArrow(gravity_arrow), FadeIn(gravity_label, shift=UP * 0.2),
                                     lag_ratio=0.25), run_time=1.2)
            self.play(falling_lid.animate.move_to(RIGHT * 3.6 + UP * 0.65),
                      gravity_arrow.animate.shift(DOWN * 1.95),
                      gravity_label.animate.shift(DOWN * 1.95),
                      run_time=1.4, rate_func=rush_into)
            self.play(Flash(falling_lid.get_center(), color=WHITE, line_length=0.2), run_time=0.5)
            self.play(FadeOut(gravity_arrow, shift=DOWN * 0.2), FadeOut(gravity_label, shift=DOWN * 0.2),
                      rate_func=rush_into, run_time=0.6)
            self.wait(max(0.1, tracker.duration - 4.2))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Let's find out!") as tracker:
            sub = self.show_subtitle("Let's find out!")
            self.play(AnimationGroup(*[Create(w) for w in wisps], lag_ratio=0.35),
                      rate_func=smooth, run_time=2.4)
            self.play(AnimationGroup(*[FadeIn(d, shift=UP * 0.4) for d in escapees], lag_ratio=0.12),
                      rate_func=smooth, run_time=1.8)
            self.play(AnimationGroup(*[d.animate.shift(UP * 1.85).set_opacity(0.0) for d in escapees],
                                     lag_ratio=0.15), rate_func=linear, run_time=2.2)
            self.play(FadeIn(steam_caption, shift=UP * 0.2), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 7.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Inside the cup, the hot liquid is made of tiny particles called molecules. These molecules move around and some escape into the air as steam.") as tracker:
            sub = self.show_subtitle("Inside the cup, the hot liquid is made of tiny particles called molecules. Some escape into the air as steam.")
            self.play(FadeOut(VGroup(*escapees), shift=UP * 0.3), FadeOut(VGroup(*wisps), shift=UP * 0.3),
                      FadeOut(steam_caption, shift=UP * 0.3), FadeOut(title_1, shift=UP * 0.3),
                      FadeOut(labels_1, shift=DOWN * 0.3), rate_func=rush_into, run_time=0.9)
            self.play(AnimationGroup(Create(zoom_panel), Create(cone_lines), lag_ratio=0.25),
                      rate_func=smooth, run_time=1.2)
            self.play(AnimationGroup(*[GrowFromCenter(d) for d in liquid_dots],
                                     *[GrowFromCenter(d) for d in gas_dots], lag_ratio=0.06),
                      rate_func=smooth, run_time=1.4)
            self.play(AnimationGroup(*[GrowArrow(a) for a in liquid_arrows],
                                     *[GrowArrow(a) for a in gas_arrows], lag_ratio=0.15),
                      rate_func=smooth, run_time=2.0)
            self.play(FadeIn(ke_formula, shift=UP * 0.2), rate_func=smooth, run_time=1.2)
            self.play(Indicate(ke_formula, color=HEAT, scale_factor=1.1), run_time=0.8)
            self.play(AnimationGroup(*[d.animate.shift(UP * 0.12) for d in liquid_dots], lag_ratio=0.05),
                      rate_func=there_and_back, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 9.3))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="But when you put a lid on the cup, it acts like a cozy blanket. It keeps the heat in and slows down the escape of steam.") as tracker:
            sub = self.show_subtitle("When you put a lid on the cup, it acts like a cozy blanket, keeping the heat in.")
            self.play(FadeOut(panel_group, shift=LEFT * 0.5), rate_func=rush_into, run_time=0.9)
            self.play(Create(barrier_line), rate_func=smooth, run_time=0.8)
            self.play(AnimationGroup(*[GrowArrow(a) for a in vapor_arrows], lag_ratio=0.25),
                      rate_func=smooth, run_time=1.6)
            self.play(FadeIn(vapor_dots), vapor_dots.animate.shift(UP * 0.45),
                      rate_func=smooth, run_time=1.0)
            self.play(Indicate(barrier_line, color=WHITE, scale_factor=1.1), run_time=0.8)
            self.play(vapor_dots.animate.shift(DOWN * 0.9),
                      vapor_arrows.animate.shift(DOWN * 0.9).set_color(COLD),
                      rate_func=smooth, run_time=1.0)
            self.play(FadeIn(condense_text, shift=UP * 0.2), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 8.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="In a cup without a lid, the heat and steam escape quickly, making the drink cool down faster.") as tracker:
            sub = self.show_subtitle("Without a lid, heat and steam escape quickly, so the drink cools faster.")
            self.play(FadeOut(vapor_dots, shift=UP * 0.3), FadeOut(vapor_arrows, shift=UP * 0.3),
                      FadeOut(barrier_line, shift=UP * 0.3), FadeOut(condense_text, shift=DOWN * 0.3),
                      FadeOut(open_cup, shift=LEFT * 0.5), FadeOut(closed_cup, shift=RIGHT * 0.5),
                      FadeOut(falling_lid, shift=RIGHT * 0.5), rate_func=rush_into, run_time=1.0)
            self.play(FadeIn(merc_L), FadeIn(merc_R), run_time=0.4, rate_func=smooth)
            self.play(AnimationGroup(FadeIn(balance_scale, shift=DOWN * 0.3),
                                     FadeIn(thermo_L, shift=UP * 0.3),
                                     FadeIn(thermo_R, shift=UP * 0.3),
                                     FadeIn(thermo_L_label), FadeIn(thermo_R_label),
                                     lag_ratio=0.25), rate_func=smooth, run_time=2.0)
            self.play(FadeIn(sixty_text, shift=UP * 0.2), rate_func=smooth, run_time=1.0)
            self.play(vt_L.animate.set_value(0.34), vt_R.animate.set_value(0.86),
                      rate_func=smooth, run_time=3.0)
            self.play(balance_scale.animate.rotate(-8 * DEGREES, about_point=pivot_point),
                      rate_func=smooth, run_time=1.5)
            self.wait(max(0.1, tracker.duration - 8.8))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="With a lid, the heat stays inside longer, and less liquid turns into steam.") as tracker:
            sub = self.show_subtitle("With a lid, heat stays inside longer and less liquid turns into steam.")
            self.remove(merc_L, merc_R)
            self.play(FadeOut(compare_group, shift=LEFT * 0.5), FadeOut(sixty_text, shift=DOWN * 0.3),
                      rate_func=rush_into, run_time=1.0)
            self.play(FadeIn(mech_cup, shift=RIGHT * 0.3), rate_func=smooth, run_time=1.2)
            self.play(AnimationGroup(
                AnimationGroup(GrowArrow(mech_arrow_1), FadeIn(mech_text_1, shift=RIGHT * 0.2), lag_ratio=0.3),
                AnimationGroup(GrowArrow(mech_arrow_2), FadeIn(mech_text_2, shift=RIGHT * 0.2), lag_ratio=0.3),
                AnimationGroup(GrowArrow(mech_arrow_3), FadeIn(mech_text_3, shift=RIGHT * 0.2), lag_ratio=0.3),
                lag_ratio=0.25), rate_func=smooth, run_time=3.2)
            self.wait(max(0.1, tracker.duration - 5.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So, the lid helps keep your drink hot and reduces the amount of liquid lost.") as tracker:
            sub = self.show_subtitle("The lid keeps your drink hot and reduces the amount of liquid lost.")
            self.play(FadeOut(mech_group, shift=RIGHT * 0.5), FadeOut(mech_cup, shift=LEFT * 0.5),
                      rate_func=rush_into, run_time=0.8)
            self.play(FadeIn(insight_main, shift=UP * 0.3), rate_func=smooth, run_time=1.6)
            self.play(Circumscribe(insight_main, color=YELLOW, buff=0.25), run_time=1.5)
            self.wait(0.5)
            self.play(Indicate(insight_main, color=HEAT, scale_factor=1.15), run_time=1.2)
            self.play(FadeIn(insight_sub, shift=UP * 0.2), rate_func=smooth, run_time=1.4)
            self.wait(max(0.1, tracker.duration - 7.2))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="It's like a little shield against the cold air outside.") as tracker:
            sub = self.show_subtitle("It's like a little shield against the cold air outside.")
            self.play(FadeOut(insight_main, shift=UP * 0.4), FadeOut(insight_sub, shift=DOWN * 0.4),
                      rate_func=rush_into, run_time=0.9)
            self.play(FadeIn(res_merc_L), FadeIn(res_merc_R), FadeIn(num_L), FadeIn(num_R), run_time=0.4, rate_func=smooth)
            self.play(FadeIn(result_group, shift=UP * 0.3), rate_func=smooth, run_time=1.2)
            self.play(temp_L.animate.set_value(61.0), temp_R.animate.set_value(79.0),
                      rate_func=smooth, run_time=3.2)
            self.play(Circumscribe(deg_R, color=HEAT, fade_out=False), run_time=1.2)
            self.play(Flash(res_thermo_R.get_top(), color=YELLOW), run_time=0.8)
            self.play(FadeIn(result_caption, shift=UP * 0.2), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 8.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Next time you enjoy a hot drink, remember how a simple lid can make a big difference in keeping it warm!") as tracker:
            sub = self.show_subtitle("Next time you enjoy a hot drink, remember how a simple lid keeps it warm!")
            self.remove(res_merc_L, res_merc_R, num_L, num_R)
            self.play(FadeOut(result_group, shift=DOWN * 0.4), FadeOut(result_caption, shift=DOWN * 0.4),
                      rate_func=rush_into, run_time=1.2)
            self.play(FadeIn(final_group, shift=UP * 0.3), rate_func=smooth, run_time=1.5)
            self.play(FadeIn(closing_line, shift=UP * 0.3), rate_func=smooth, run_time=1.4)
            self.play(Indicate(final_lid, scale_factor=1.12, color=LIDC), run_time=1.0)
            self.wait(1.0)
            self.play(FadeOut(final_group, shift=UP * 0.3), FadeOut(closing_line, shift=DOWN * 0.3),
                      rate_func=smooth, run_time=1.6)
            self.wait(max(0.1, tracker.duration - 8.5))
            self.play(FadeOut(sub), run_time=0.4)