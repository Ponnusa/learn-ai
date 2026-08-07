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


class WhyIsMyDrinkStillHot(VoiceoverScene):
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

        # ═══ SETUP BLOCK: define every object used below BEFORE the first voiceover ═══
        INSIGHT = ManimColor("#FFD166")
        HOT = ManimColor("#EF476F")

        background = Rectangle(width=15, height=9, fill_color="#0D1117",
                                fill_opacity=1, stroke_width=0).move_to(ORIGIN)

        # --- Intro cup / lid / thermometer / steam ---
        CUP = RoundedRectangle(corner_radius=0.15, width=2.2, height=2.6,
                                color=WHITE, fill_opacity=0.05).move_to(ORIGIN)
        LID = Rectangle(width=2.3, height=0.3, color=GRAY_B, fill_opacity=1).move_to(
            CUP.get_top() + UP * 0.15)
        thermo1 = get_svg("thermometer", height=1.0).next_to(CUP, RIGHT, buff=0.5)
        temp_label1 = Text("95°C", font_size=28, color=HOT).next_to(thermo1, UP, buff=0.2)
        STEAM = VGroup(*[
            ParametricFunction(
                lambda t, i=i: np.array([np.sin(t * 2 + i) * 0.15 + (i - 1) * 0.3, t * 0.5, 0]),
                t_range=[0, 1.5], color=WHITE)
            for i in range(3)
        ]).next_to(CUP, UP, buff=0.1)

        # --- "Three hours later" ---
        question_text = Text("3 hours later...", font_size=32).move_to(UP * 1.5)
        question_mark = Text("?", font_size=90, color=YELLOW).move_to(ORIGIN)
        dashed_circle = DashedVMobject(Circle(radius=1.3, color=YELLOW), num_dashes=24).move_to(ORIGIN)

        # --- Three cups comparison ---
        table_line = Line(LEFT * 6, RIGHT * 6, color=GRAY).shift(DOWN * 2.5)
        t_mug = ValueTracker(95.0)
        t_paper = ValueTracker(95.0)
        t_thermos = ValueTracker(95.0)
        mug_icon = Square(side_length=1.0, color=WHITE).move_to(np.array([-4, 0.3, 0]))
        paper_icon = Square(side_length=1.0, color=WHITE).move_to(np.array([0, 0.3, 0]))
        thermos_icon = Square(side_length=1.0, color=WHITE).move_to(np.array([4, 0.3, 0]))
        mug_label = Text("Mug", font_size=22).next_to(mug_icon, DOWN)
        paper_label = Text("Paper Cup", font_size=22).next_to(paper_icon, DOWN)
        thermos_label = Text("Thermos", font_size=22).next_to(thermos_icon, DOWN)
        mug_grp = VGroup(mug_icon, mug_label)
        paper_grp = VGroup(paper_icon, paper_label)
        thermos_grp = VGroup(thermos_icon, thermos_label)
        mug_num = DecimalNumber(t_mug.get_value(), num_decimal_places=0, font_size=24).next_to(mug_label, DOWN)
        mug_num.add_updater(lambda d: d.set_value(t_mug.get_value()))
        paper_num = DecimalNumber(t_paper.get_value(), num_decimal_places=0, font_size=24).next_to(paper_label, DOWN)
        paper_num.add_updater(lambda d: d.set_value(t_paper.get_value()))
        thermos_num = DecimalNumber(t_thermos.get_value(), num_decimal_places=0, font_size=24).next_to(thermos_label, DOWN)
        thermos_num.add_updater(lambda d: d.set_value(t_thermos.get_value()))

        # --- Lid section ---
        arrow_l = Arrow(np.array([-2.2, 0.6, 0]), np.array([-3.2, 1.4, 0]), color=HOT, buff=0)
        arrow_up = Arrow(np.array([-2.2, 0.6, 0]), np.array([-2.2, 1.8, 0]), color=HOT, buff=0)
        arrow_r = Arrow(np.array([-2.2, 0.6, 0]), np.array([-1.2, 1.4, 0]), color=HOT, buff=0)
        escape_arrows = VGroup(arrow_l, arrow_up, arrow_r)
        lid_note = Text("Lid blocks heat loss", font_size=22).move_to(np.array([-2.2, -2.0, 0]))

        # --- Double wall / vacuum gap section ---
        cross_section = Rectangle(width=2.2, height=2.6, color=WHITE, fill_opacity=0.05).move_to(
            np.array([-2.2, -0.3, 0]))
        hatch = VGroup(*[
            Line(np.array([-2.2 - 0.9 + 0.3 * i, -0.3 - 1.1, 0]),
                 np.array([-2.2 - 0.7 + 0.3 * i, -0.3 - 0.9, 0]), color=GRAY)
            for i in range(6)
        ])
        gap_pointer = Arrow(np.array([-1.0, -0.3, 0]), np.array([-1.9, -0.3, 0]), color=YELLOW, buff=0)
        gap_label = Text("Vacuum Gap", font_size=20, color=YELLOW).next_to(gap_pointer, RIGHT)
        gap_brace = Brace(cross_section, direction=RIGHT)
        gap_brace_label = gap_brace.get_text("Insulation")

        # --- Heat transfer methods section ---
        cond_arrow = Arrow(LEFT * 3 + UP * 1, LEFT * 1 + UP * 1, color=HOT, buff=0)
        conv_arrow = Arrow(UP * 0.5, UP * 2, color=HOT, buff=0)
        rad_arrow = Arrow(RIGHT * 1 + UP * 1, RIGHT * 3 + UP * 1, color=HOT, buff=0)
        transport_arrows = VGroup(cond_arrow, conv_arrow, rad_arrow)
        crosses = VGroup(*[Cross(scale_factor=0.3).move_to(a.get_center()) for a in transport_arrows])
        three_labels = VGroup(
            Text("Conduction", font_size=20).next_to(cond_arrow, DOWN),
            Text("Convection", font_size=20).next_to(conv_arrow, UP),
            Text("Radiation", font_size=20).next_to(rad_arrow, DOWN),
        )

        # --- Material swatches section ---
        swatches = VGroup(*[
            Square(side_length=0.8, fill_opacity=1, color=c).move_to(np.array([x, 0.5, 0]))
            for x, c in zip([-3, -1, 1, 3], [GRAY, ORANGE, BLUE, WHITE])
        ])
        sw_labels = VGroup(*[
            Text(t, font_size=20).next_to(s, DOWN)
            for t, s in zip(["Metal", "Plastic", "Glass", "Ceramic"], swatches)
        ])
        k_labels = VGroup(*[
            Text(f"k={v}", font_size=18).next_to(s, DOWN, buff=0.8)
            for v, s in zip([205, 0.2, 1.0, 1.5], swatches)
        ])
        k_bars = VGroup(*[
            Rectangle(width=0.3, height=max(0.05, v * 0.01), fill_opacity=1, color=YELLOW,
                      stroke_width=0).next_to(s, DOWN, buff=1.3)
            for v, s in zip([205, 0.2, 1.0, 1.5], swatches)
        ])

        # --- Metal vs vacuum flask over time ---
        t_metal = ValueTracker(95.0)
        t_vac = ValueTracker(95.0)
        metal_icon = Circle(radius=0.6, color=GRAY_B, fill_opacity=1).move_to(np.array([-3.5, 0.5, 0]))
        vac_icon = Circle(radius=0.6, color=GRAY_A, fill_opacity=1).move_to(np.array([3.5, 0.5, 0]))
        metal_grp = VGroup(metal_icon)
        vac_grp = VGroup(vac_icon)
        metal_title = Text("Bare Metal Cup", font_size=24).next_to(metal_icon, UP)
        vac_title = Text("Vacuum Flask", font_size=24).next_to(vac_icon, UP)
        metal_num = DecimalNumber(t_metal.get_value(), num_decimal_places=0, font_size=30).move_to(
            np.array([-3.5, -2.0, 0]))
        metal_num.add_updater(lambda d: d.set_value(t_metal.get_value()))
        vac_num = DecimalNumber(t_vac.get_value(), num_decimal_places=0, font_size=30).move_to(
            np.array([3.5, -2.0, 0]))
        vac_num.add_updater(lambda d: d.set_value(t_vac.get_value()))
        metal_col = Rectangle(width=4, height=4, color=RED, fill_opacity=0.08, stroke_width=0).move_to(
            np.array([-3.5, 0, 0]))
        vac_col = Rectangle(width=4, height=4, color=BLUE, fill_opacity=0.08, stroke_width=0).move_to(
            np.array([3.5, 0, 0]))
        split_line = Line(UP * 3, DOWN * 3, color=GRAY)
        loss_arrows = VGroup(*[
            Arrow(metal_icon.get_center() + d * 0.7, metal_icon.get_center() + d * 1.4, color=HOT, buff=0)
            for d in [UP, LEFT, RIGHT, UP + LEFT]
        ])

        # --- Insight summary ---
        insight_text = Text("Lid + Double Walls + Right Material = Cold Drink",
                             font_size=28, color=INSIGHT).move_to(UP * 0.5)
        chips = VGroup(*[
            Circle(radius=0.15, color=BLUE, fill_opacity=1).move_to(np.array([i * 0.5 - 1.0, -1.0, 0]))
            for i in range(5)
        ])

        # --- Result: 78 degrees after 6 hours ---
        t_result = ValueTracker(95.0)
        result_thermo = get_svg("thermometer", height=1.2).move_to(np.array([0, 0.5, 0]))
        result_unit = Text("°C", font_size=36).next_to(result_thermo, RIGHT, buff=1.0)
        result_num = DecimalNumber(t_result.get_value(), num_decimal_places=0, font_size=48).next_to(
            result_unit, LEFT, buff=0.1)
        result_num.add_updater(lambda d: d.set_value(t_result.get_value()))
        result_group = VGroup(result_thermo, result_unit, result_num)
        result_caption = Text("Still warm after 6 hours!", font_size=24).next_to(result_group, DOWN, buff=0.5)

        # --- Hill / slope scene ---
        hill_start = np.array([-6.0, -0.25, 0])
        hill_end = np.array([-6.0 + 9.2, -0.25 - 1.65, 0])
        hill = ArcBetweenPoints(hill_start, hill_end, angle=-TAU / 8, color=GREEN, stroke_width=6)
        hill_path = hill.copy()
        hill_fill = Polygon(
            hill_start, hill_end,
            np.array([hill_end[0], -3.5, 0]), np.array([hill_start[0], -3.5, 0]),
            color=GREEN, fill_opacity=0.15, stroke_width=0
        )
        sun = Circle(radius=0.5, color=YELLOW, fill_opacity=1).move_to(np.array([4.5, 3, 0]))

        slope_vec = hill_end - hill_start
        _perp = np.array([-slope_vec[1], slope_vec[0], 0])
        normal_unit = _perp / np.linalg.norm(_perp)
        gravity_arrow = Arrow(hill_start, hill_start + DOWN * 1.0, color=WHITE, buff=0.05, stroke_width=4)
        normal_arrow = Arrow(hill_start, hill_start + normal_unit * 1.0, color=BLUE, buff=0.05, stroke_width=4)

        blanket_grp = VGroup(
            Rectangle(width=1.0, height=1.3, color=RED, fill_opacity=0.3).move_to(hill_end + UP * 0.6),
            Text("Insulated!", font_size=20, color=RED).move_to(hill_end + UP * 1.3)
        )

        # --- Final scene ---
        final_thermo = get_svg("thermometer", height=1.0).move_to(np.array([-3.5, 0.5, 0]))
        final_num = DecimalNumber(78, num_decimal_places=0, font_size=36).next_to(final_thermo, RIGHT)
        answer_text = Text("Vacuum insulation — not magic!", font_size=28, color=INSIGHT).move_to(DOWN * 2)

        self.add(background)
        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Imagine you're at a picnic on a hot day. You want your drink to stay cold. But how does your cup help with that?") as tracker:
            sub = self.show_subtitle("Imagine you're at a picnic on a hot day. You want your drink to stay cold. But how does your cup help with that?")
            self.play(DrawBorderThenFill(CUP), run_time=2.2, rate_func=smooth)
            self.play(FadeIn(LID, shift=DOWN * 0.5), run_time=1.0, rate_func=smooth)
            self.play(FadeIn(thermo1, shift=UP * 0.6), run_time=1.2, rate_func=smooth)
            self.play(FadeIn(temp_label1, shift=UP * 0.2), run_time=0.8, rate_func=smooth)
            self.play(Create(STEAM, lag_ratio=0.3), run_time=1.5, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 7.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Three hours later, is it still hot?") as tracker:
            sub = self.show_subtitle("Three hours later, is it still hot?")
            self.play(FadeIn(question_text, shift=DOWN * 0.4), run_time=1.2, rate_func=smooth)
            self.play(Create(question_mark), run_time=1.8, rate_func=smooth)
            self.play(Create(dashed_circle), run_time=1.0, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 4.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Let's explore the features of a cup that keep your drink chilly. First, think about a lid.") as tracker:
            sub = self.show_subtitle("Let's explore the features of a cup that keep your drink chilly. First, think about a lid.")
            self.play(FadeOut(question_mark, shift=RIGHT * 0.5), FadeOut(dashed_circle),
                      FadeOut(question_text, shift=UP * 0.3), FadeOut(STEAM),
                      FadeOut(temp_label1), FadeOut(thermo1, shift=UP * 0.3),
                      run_time=0.9, rate_func=rush_into)
            self.play(FadeOut(CUP, shift=LEFT * 0.5), FadeOut(LID, shift=LEFT * 0.5),
                      run_time=1.0, rate_func=rush_into)
            self.play(Create(table_line), run_time=0.8, rate_func=smooth)
            self.play(FadeIn(mug_num, paper_num, thermos_num), run_time=0.4)
            self.play(AnimationGroup(FadeIn(mug_grp, shift=UP * 0.4), FadeIn(paper_grp, shift=UP * 0.4),
                                     FadeIn(thermos_grp, shift=UP * 0.4), lag_ratio=0.25),
                      run_time=2.4, rate_func=smooth)
            self.play(t_mug.animate.set_value(45.0), t_paper.animate.set_value(38.0),
                      t_thermos.animate.set_value(82.0), run_time=3.0, rate_func=linear)
            self.wait(max(0.1, tracker.duration - 8.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="A lid acts like a shield, keeping warm air out and cold air in. It's like putting a hat on your drink!") as tracker:
            sub = self.show_subtitle("A lid acts like a shield, keeping warm air out and cold air in. It's like putting a hat on your drink!")
            self.play(FadeOut(mug_grp, shift=LEFT * 0.5), FadeOut(paper_grp, shift=DOWN * 0.5),
                      FadeOut(thermos_grp, shift=RIGHT * 0.5), FadeOut(table_line),
                      FadeOut(mug_num), FadeOut(paper_num), FadeOut(thermos_num),
                      run_time=0.9, rate_func=rush_into)
            CUP.move_to(np.array([-2.2, -0.3, 0])).scale(0.9)
            LID.move_to(np.array([-2.2, 2.2, 0])).scale(0.9)
            self.play(FadeIn(CUP, shift=UP * 0.3), run_time=1.0, rate_func=smooth)
            self.play(AnimationGroup(GrowArrow(arrow_l), GrowArrow(arrow_up), GrowArrow(arrow_r),
                                     lag_ratio=0.25), run_time=1.6)
            self.play(LID.animate.move_to(np.array([-2.2, 1.05, 0])),
                      escape_arrows.animate.set_color(GRAY).set_opacity(0.3),
                      FadeIn(lid_note, shift=LEFT * 0.3), run_time=1.4, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 5.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Next, consider double walls. These are like a cozy blanket for your drink. They trap the cold inside and keep the heat out.") as tracker:
            sub = self.show_subtitle("Next, consider double walls. These are like a cozy blanket for your drink. They trap the cold inside and keep the heat out.")
            self.play(FadeOut(escape_arrows, shift=UP * 0.4), FadeOut(lid_note, shift=RIGHT * 0.4),
                      FadeOut(LID, shift=UP * 0.5), run_time=0.9, rate_func=rush_into)
            self.play(Transform(CUP, cross_section), run_time=1.6, rate_func=smooth)
            self.play(AnimationGroup(*[Create(h) for h in hatch], lag_ratio=0.25),
                      run_time=1.8, rate_func=smooth)
            self.play(GrowArrow(gap_pointer), run_time=0.9)
            self.play(FadeIn(gap_label, shift=LEFT * 0.2), run_time=1.0, rate_func=smooth)
            self.play(FadeIn(gap_brace), FadeIn(gap_brace_label), run_time=0.8, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 7.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Heat tries three ways out: conduction, convection, and radiation. The vacuum gap stops them all.") as tracker:
            sub = self.show_subtitle("Heat tries three ways out: conduction, convection, and radiation. The vacuum gap stops them all.")
            self.play(FadeOut(gap_brace), FadeOut(gap_brace_label),
                      FadeOut(gap_pointer, shift=RIGHT * 0.3), FadeOut(gap_label, shift=RIGHT * 0.3),
                      run_time=0.8, rate_func=rush_into)
            self.play(AnimationGroup(GrowArrow(cond_arrow), GrowArrow(conv_arrow), GrowArrow(rad_arrow),
                                     lag_ratio=0.25), run_time=2.2, rate_func=smooth)
            self.play(AnimationGroup(*[FadeIn(x, scale=1.4) for x in crosses], lag_ratio=0.25),
                      run_time=1.4, rate_func=smooth)
            self.play(transport_arrows.animate.set_color(GRAY).set_opacity(0.35),
                      run_time=1.0, rate_func=smooth)
            self.play(AnimationGroup(*[FadeIn(l, shift=LEFT * 0.2) for l in three_labels], lag_ratio=0.25),
                      run_time=1.2, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 7.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Finally, the material of the cup matters. Some materials, like metal, are better at keeping drinks cold than others, like plastic.") as tracker:
            sub = self.show_subtitle("Finally, the material of the cup matters. Some materials conduct heat quickly, others barely at all.")
            self.play(FadeOut(transport_arrows), FadeOut(crosses), FadeOut(three_labels),
                      FadeOut(hatch), FadeOut(CUP, shift=DOWN * 0.5), run_time=0.9, rate_func=rush_into)
            self.play(AnimationGroup(*[DrawBorderThenFill(s) for s in swatches], lag_ratio=0.25),
                      run_time=2.0, rate_func=smooth)
            self.play(AnimationGroup(*[FadeIn(l, shift=DOWN * 0.2) for l in sw_labels], lag_ratio=0.25),
                      run_time=1.0, rate_func=smooth)
            self.play(AnimationGroup(*[FadeIn(k, shift=UP * 0.2) for k in k_labels], lag_ratio=0.25),
                      run_time=1.6, rate_func=smooth)
            self.play(AnimationGroup(*[GrowFromEdge(b, LEFT) for b in k_bars], lag_ratio=0.25),
                      run_time=1.6, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 7.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Watch what happens over time. A bare metal cup dumps its heat, while the vacuum flask barely changes.") as tracker:
            sub = self.show_subtitle("A bare metal cup dumps its heat, while the vacuum flask barely changes.")
            self.play(FadeOut(swatches, shift=UP * 0.4), FadeOut(sw_labels, shift=UP * 0.4),
                      FadeOut(k_labels), FadeOut(k_bars), run_time=0.9, rate_func=rush_into)
            self.play(FadeIn(metal_num, vac_num, metal_col, vac_col), run_time=0.4)
            self.play(Create(split_line), run_time=0.6, rate_func=smooth)
            self.play(AnimationGroup(FadeIn(metal_grp, shift=RIGHT * 0.5), FadeIn(vac_grp, shift=LEFT * 0.5),
                                     lag_ratio=0.25), run_time=1.6, rate_func=smooth)
            self.play(FadeIn(metal_title, shift=DOWN * 0.2), FadeIn(vac_title, shift=DOWN * 0.2),
                      run_time=0.8, rate_func=smooth)
            self.play(AnimationGroup(*[GrowArrow(a) for a in loss_arrows], lag_ratio=0.25), run_time=1.4)
            self.play(t_metal.animate.set_value(42.0), t_vac.animate.set_value(80.0),
                      run_time=3.5, rate_func=linear)
            self.wait(max(0.1, tracker.duration - 9.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So, if your cup has a lid, double walls, and is made of the right material, your drink stays cold longer.") as tracker:
            sub = self.show_subtitle("A lid, double walls, and the right material together keep your drink cold longer.")
            self.play(FadeOut(metal_grp, shift=LEFT * 0.5), FadeOut(vac_grp, shift=RIGHT * 0.5),
                      FadeOut(loss_arrows), FadeOut(metal_title), FadeOut(vac_title),
                      FadeOut(split_line), FadeOut(metal_col), FadeOut(vac_col),
                      FadeOut(metal_num), FadeOut(vac_num),
                      run_time=1.0, rate_func=rush_into)
            self.play(FadeIn(insight_text, shift=UP * 0.3), run_time=1.0, rate_func=smooth)
            self.wait(0.5)
            self.play(Circumscribe(insight_text, color=INSIGHT, buff=0.25), run_time=1.6)
            self.play(FadeIn(chips, shift=UP * 0.2), run_time=0.8, rate_func=smooth)
            self.play(Indicate(chips, scale_factor=1.15, color=INSIGHT), run_time=1.4)
            self.wait(max(0.1, tracker.duration - 7.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="After six hours, the drink inside a good vacuum flask is still seventy eight degrees.") as tracker:
            sub = self.show_subtitle("After six hours, the drink inside a good vacuum flask is still 78 degrees.")
            self.play(FadeOut(insight_text, shift=UP * 0.4), FadeOut(chips, shift=DOWN * 0.4),
                      run_time=0.9, rate_func=rush_into)
            self.play(FadeIn(result_thermo, shift=UP * 0.4), FadeIn(result_unit),
                      FadeIn(result_num), run_time=1.0, rate_func=smooth)
            self.play(t_result.animate.set_value(78.0), run_time=1.8, rate_func=rush_from)
            self.play(Circumscribe(result_group, color=INSIGHT), run_time=1.2)
            self.play(Flash(result_thermo.get_bottom(), color=HOT, num_lines=12), run_time=0.6)
            self.play(FadeIn(result_caption, shift=UP * 0.2), run_time=0.8, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 6.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Next time you're at a picnic, you'll know exactly which cup to choose to keep your drink refreshingly cold.") as tracker:
            sub = self.show_subtitle("Next time you're at a picnic, you'll know exactly which cup to choose.")
            self.play(FadeOut(result_thermo, shift=UP * 0.4), FadeOut(result_group),
                      FadeOut(result_caption, shift=RIGHT * 0.4), run_time=0.9, rate_func=rush_into)
            self.play(FadeIn(hill_fill), Create(hill), FadeIn(sun), run_time=1.2, rate_func=smooth)
            CUP.scale(0.65).move_to(np.array([-6.0, -0.25, 0]))
            self.play(FadeIn(CUP, shift=UP * 0.3), run_time=0.8, rate_func=smooth)
            self.play(GrowArrow(gravity_arrow), GrowArrow(normal_arrow), run_time=1.0)
            self.play(MoveAlongPath(CUP, hill_path),
                      gravity_arrow.animate.shift(np.array([9.2, -1.65, 0])),
                      normal_arrow.animate.shift(np.array([9.2, -1.65, 0])),
                      run_time=3.2, rate_func=smooth)
            self.play(FadeIn(blanket_grp, shift=UP * 0.3), run_time=0.8, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 8.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Still hot after three hours? Yes — vacuum, not magic.") as tracker:
            sub = self.show_subtitle("Still hot after three hours? Yes — vacuum, not magic.")
            self.play(FadeOut(hill), FadeOut(hill_fill), FadeOut(blanket_grp),
                      FadeOut(sun), FadeOut(gravity_arrow), FadeOut(normal_arrow),
                      run_time=1.0, rate_func=rush_into)
            self.play(CUP.animate.move_to(np.array([-1.8, -0.4, 0])).scale(1.3),
                      run_time=1.4, rate_func=smooth)
            self.play(FadeIn(final_thermo, shift=UP * 0.3), FadeIn(final_num, shift=UP * 0.3),
                      run_time=1.0, rate_func=smooth)
            self.play(FadeIn(answer_text, shift=DOWN * 0.3), run_time=1.2, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 5.2))
            self.play(FadeOut(sub), run_time=0.4)

        self.play(FadeOut(CUP), FadeOut(final_thermo), FadeOut(final_num),
                  FadeOut(answer_text), run_time=2.0, rate_func=rush_into)