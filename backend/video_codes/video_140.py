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
        self.camera.background_color = ManimColor("#0E1117")

        # ═══ SETUP BLOCK: define all objects used across voiceover beats ═══
        COLD = BLUE
        HOT = RED
        ACCENT = YELLOW

        background = Rectangle(width=15, height=9, fill_color=self.camera.background_color,
                                fill_opacity=1, stroke_width=0)

        question = Text("Can a cup that keeps your drink cold\nalso keep it hot?",
                         font_size=32, color=WHITE).move_to(UP * 1.0)
        underline = Line(question.get_corner(DL) + DOWN * 0.2, question.get_corner(DR) + DOWN * 0.2,
                          color=ACCENT)

        # Plain cup
        plain_body = RoundedRectangle(width=1.4, height=1.8, corner_radius=0.1, color=WHITE)
        plain_liquid = Rectangle(width=1.0, height=0.9, fill_color=COLD, fill_opacity=1, stroke_width=0)
        plain_liquid.move_to(plain_body.get_center() + DOWN * 0.3)
        plain_cup = VGroup(plain_body, plain_liquid)
        plain_lid = Rectangle(width=1.5, height=0.15, fill_color=GRAY, fill_opacity=1, stroke_width=0)

        # Insulated cup
        insul_body = RoundedRectangle(width=1.6, height=2.0, corner_radius=0.1, color=WHITE)
        insul_liquid = Rectangle(width=1.1, height=1.0, fill_color=COLD, fill_opacity=1, stroke_width=0)
        insul_liquid.move_to(insul_body.get_center() + DOWN * 0.3)
        insul_cup = VGroup(insul_body, insul_liquid).move_to(RIGHT * 3.2 + DOWN * 0.3)

        label_plain = Text("Plain Cup", font_size=20, color=WHITE)
        label_insul = Text("Insulated Cup", font_size=20, color=WHITE)

        heat_in = VGroup(*[
            Arrow(LEFT * 5.5 + UP * (i * 0.5 - 0.5), LEFT * 4.0 + UP * (i * 0.5 - 0.5), color=RED, buff=0)
            for i in range(3)
        ])
        heat_in_label = Text("Heat flows in", font_size=20, color=RED).next_to(heat_in, UP * 0.3)
        droplets = VGroup(*[Dot(radius=0.05, color=BLUE) for _ in range(5)]).arrange(RIGHT, buff=0.15).move_to(DOWN * 2.5)

        steam = VGroup(*[
            Line(ORIGIN, UP * 0.4, color=WHITE).shift(RIGHT * i * 0.2 + UP * 1.5)
            for i in range(-1, 2)
        ]).move_to(insul_cup.get_top() + UP * 0.6)
        steam_plain = steam.copy().move_to(plain_cup.get_top() + UP * 0.6)

        heat_out = VGroup(*[
            Arrow(LEFT * 4.0 + UP * (i * 0.5 - 0.5), LEFT * 5.5 + UP * (i * 0.5 - 0.5), color=ORANGE, buff=0)
            for i in range(3)
        ])

        feature_cup = RoundedRectangle(width=1.8, height=2.2, corner_radius=0.15, color=WHITE).move_to(LEFT * 3)
        feature_lid = Ellipse(width=1.9, height=0.3, color=GRAY, fill_color=GRAY, fill_opacity=1).move_to(feature_cup.get_top())

        bullets = VGroup(
            Text("- Insulated walls", font_size=22),
            Text("- Airtight lid", font_size=22),
            Text("- Vacuum gap", font_size=22),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.3).move_to(RIGHT * 2.5)

        def safe_dashed_line(p1, p2, **kwargs):
            p1a, p2a = np.array(p1), np.array(p2)
            if np.linalg.norm(p2a - p1a) > 0.01:
                return DashedLine(p1a, p2a, **kwargs)
            return DashedLine(p1a, p1a + RIGHT * 0.01, **kwargs)

        dashes = VGroup(*[
            safe_dashed_line(feature_cup.get_right() + UP * (0.5 - i * 0.5), b.get_left(), color=GRAY)
            for i, b in enumerate(bullets)
        ])

        outer_wall = RoundedRectangle(width=2.0, height=2.2, corner_radius=0.15, color=WHITE)
        vacuum_gap = RoundedRectangle(width=1.7, height=1.9, corner_radius=0.12, color=GRAY)
        inner_wall = RoundedRectangle(width=1.4, height=1.6, corner_radius=0.1, color=WHITE)
        layers = VGroup(inner_wall, vacuum_gap, outer_wall)

        explode_lid = Rectangle(width=1.5, height=0.15, fill_color=GRAY, fill_opacity=1, stroke_width=0)
        lid_top = UP * 2.6
        lid_seat = outer_wall.get_top()
        gravity_arrow = Arrow(UP * 2.2, UP * 1.6, color=YELLOW, buff=0)
        vac_label = Text("Vacuum traps heat", font_size=20, color=ACCENT).move_to(DOWN * 2.2)

        # Experiment setup
        exp_plain = VGroup(plain_body.copy(), plain_liquid.copy()).move_to(LEFT * 3)
        exp_insul = VGroup(insul_body.copy(), insul_liquid.copy()).move_to(RIGHT * 3)
        exp_lid = Rectangle(width=1.7, height=0.15, fill_color=GRAY, fill_opacity=1, stroke_width=0).move_to(exp_insul.get_top() + UP * 0.05)
        exp_label_p = Text("No lid", font_size=20).next_to(exp_plain, DOWN, buff=0.3)
        exp_label_i = Text("Lid + insulation", font_size=20).next_to(exp_insul, DOWN, buff=0.3)

        thermo_p = get_svg("thermometer", height=0.6).next_to(exp_plain, UP, buff=0.2)
        thermo_i = get_svg("thermometer", height=0.6).next_to(exp_insul, UP, buff=0.2)
        thermo_p_target = exp_plain.get_top() + UP * 0.4
        thermo_i_target = exp_insul.get_top() + UP * 0.4

        start_label = Text("t = 0s", font_size=20).move_to(UP * 2.8)

        t_tracker = ValueTracker(0)
        temp_p = ValueTracker(80.0)
        temp_i = ValueTracker(80.0)

        num_p = DecimalNumber(80.0, num_decimal_places=1, font_size=28, color=COLD)
        num_p.add_updater(lambda d: d.set_value(temp_p.get_value()))
        num_p.move_to(exp_plain.get_center() + UP * 1.6)
        num_i = DecimalNumber(80.0, num_decimal_places=1, font_size=28, color=HOT)
        num_i.add_updater(lambda d: d.set_value(temp_i.get_value()))
        num_i.move_to(exp_insul.get_center() + UP * 1.9)
        clock_num = DecimalNumber(0, num_decimal_places=0, font_size=24, color=WHITE)
        clock_num.add_updater(lambda d: d.set_value(t_tracker.get_value()))
        clock_num.move_to(UP * 3.2)

        unit_p = Text("C", font_size=20, color=COLD).next_to(num_p, RIGHT, buff=0.1)
        unit_i = Text("C", font_size=20, color=HOT).next_to(num_i, RIGHT, buff=0.1)
        clock_label = Text("seconds", font_size=20, color=WHITE).next_to(clock_num, RIGHT, buff=0.1)

        exp_heat_out = VGroup(*[
            Arrow(exp_plain.get_top() + UP * (0.3 + i * 0.3), exp_plain.get_top() + UP * (0.8 + i * 0.3), color=ORANGE, buff=0)
            for i in range(2)
        ])

        res_plain_num = Text("42C", font_size=32, color=COLD).move_to(LEFT * 3 + DOWN * 2.5)
        res_plain_unit = Text("(cooled a lot)", font_size=18, color=WHITE).next_to(res_plain_num, DOWN, buff=0.2)
        res_insul_num = Text("84C", font_size=32, color=HOT).move_to(RIGHT * 3 + DOWN * 2.5)
        res_insul_unit = Text("(stayed hot!)", font_size=18, color=WHITE).next_to(res_insul_num, DOWN, buff=0.2)

        insul_group = VGroup(exp_insul, exp_lid, res_insul_num, res_insul_unit)

        delta_tex = MathTex(r"\Delta T_{insulated} \ll \Delta T_{plain}", font_size=32, color=ACCENT).move_to(DOWN * 2.8)

        # Hero cup
        hero_cup = RoundedRectangle(width=1.8, height=2.2, corner_radius=0.15, color=WHITE).move_to(DOWN * 0.3)
        hero_lid = Rectangle(width=1.9, height=0.2, fill_color=GRAY, fill_opacity=1, stroke_width=0).move_to(hero_cup.get_top())
        blocked_arrow = Arrow(hero_cup.get_left() + LEFT * 1.5, hero_cup.get_left(), color=RED, buff=0)
        blocked_arrow2 = Arrow(hero_cup.get_right() + RIGHT * 1.5, hero_cup.get_right(), color=RED, buff=0)
        blocked_group = VGroup(blocked_arrow, blocked_arrow2)
        cross_group = VGroup(
            Cross(scale_factor=0.2).move_to(hero_cup.get_left() + LEFT * 0.7),
            Cross(scale_factor=0.2).move_to(hero_cup.get_right() + RIGHT * 0.7),
        )
        stopped_label = Text("Heat Blocked!", font_size=24, color=ACCENT).next_to(hero_cup, DOWN, buff=0.5)
        thermo_hero = get_svg("thermometer", height=0.6).next_to(hero_cup, UP, buff=0.2)
        hero_num = Text("84C", font_size=28, color=HOT).next_to(thermo_hero, RIGHT, buff=0.2)
        hero_unit = Text("after 60s", font_size=18, color=WHITE).next_to(hero_num, DOWN, buff=0.1)

        answer = Text("Yes! With the right design.", font_size=32, color=ACCENT).move_to(UP * 1.0)

        final_cup = RoundedRectangle(width=1.8, height=2.2, corner_radius=0.15, color=WHITE).move_to(DOWN * 0.3)
        final_lid = Rectangle(width=1.9, height=0.2, fill_color=GRAY, fill_opacity=1, stroke_width=0).move_to(final_cup.get_top())
        thermo_final = get_svg("thermometer", height=0.6).next_to(final_cup, UP, buff=0.2)
        final_num = Text("Just Right!", font_size=28, color=ACCENT).next_to(thermo_final, RIGHT, buff=0.2)
        final_unit = Text("Hot & Cold", font_size=18, color=WHITE).next_to(final_num, DOWN, buff=0.1)
        final_caption = Text("Perfectly insulated!", font_size=22, color=WHITE).next_to(final_cup, DOWN, buff=0.5)

        self.add(background)
        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Can a cup that keeps your drink cold also keep it hot?") as tracker:
            sub = self.show_subtitle("Can a cup that keeps your drink cold also keep it hot?")
            self.play(FadeIn(question, shift=DOWN * 0.6), run_time=1.4, rate_func=smooth)
            self.play(Create(underline), run_time=0.8, rate_func=smooth)
            self.wait(0.5)
            self.play(question.animate.scale(0.6).to_edge(UP, buff=0.4),
                      FadeOut(underline, shift=UP * 0.3), run_time=0.9, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 3.8))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Let's find out!") as tracker:
            sub = self.show_subtitle("Let's find out!")
            plain_cup.move_to(LEFT * 7 + DOWN * 0.4)
            plain_lid.move_to(plain_cup.get_top() + UP * 0.1)
            self.play(DrawBorderThenFill(plain_body), run_time=1.2, rate_func=smooth)
            self.play(FadeIn(plain_liquid, shift=UP * 0.3), run_time=0.7, rate_func=rush_from)
            self.play(plain_cup.animate.move_to(DOWN * 0.3), run_time=1.2, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 3.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Imagine you have a cup that keeps your soda icy cold.") as tracker:
            sub = self.show_subtitle("Imagine you have a cup that keeps your soda icy cold.")
            label_plain.next_to(LEFT * 3.2 + DOWN * 0.3, DOWN, buff=1.4)
            label_insul.next_to(insul_cup, DOWN, buff=0.3)
            self.play(AnimationGroup(
                plain_cup.animate.move_to(LEFT * 3.2 + DOWN * 0.3),
                FadeIn(insul_cup, shift=RIGHT * 0.8),
                FadeIn(label_plain, shift=UP * 0.2),
                FadeIn(label_insul, shift=UP * 0.2),
                lag_ratio=0.25), run_time=2.2, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 2.8))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Now, what if you pour hot chocolate into it?") as tracker:
            sub = self.show_subtitle("Now, what if you pour hot chocolate into it?")
            self.play(plain_liquid.animate.set_fill(COLD),
                      insul_liquid.animate.set_fill(COLD), run_time=0.7, rate_func=smooth)
            self.play(AnimationGroup(*[GrowArrow(a) for a in heat_in], lag_ratio=0.25),
                      run_time=1.3)
            self.play(FadeIn(heat_in_label, shift=UP * 0.2),
                      FadeIn(droplets), run_time=0.8, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 3.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Will it stay hot?") as tracker:
            sub = self.show_subtitle("Will it stay hot?")
            self.play(plain_liquid.animate.set_fill(HOT), insul_liquid.animate.set_fill(HOT),
                      FadeOut(heat_in, shift=DOWN * 0.2), FadeOut(droplets),
                      FadeOut(heat_in_label, shift=UP * 0.2), run_time=1.0, rate_func=smooth)
            self.play(FadeIn(steam, shift=UP * 0.5), FadeIn(steam_plain, shift=UP * 0.5),
                      run_time=1.0, rate_func=smooth)
            self.play(AnimationGroup(*[GrowArrow(a) for a in heat_out], lag_ratio=0.25),
                      run_time=1.2)
            self.wait(max(0.1, tracker.duration - 3.8))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Here's the secret: cups with lids and multiple walls are like little jackets for your drinks.") as tracker:
            sub = self.show_subtitle("Cups with lids and multiple walls are like little jackets for your drinks.")
            self.play(FadeOut(plain_cup, shift=LEFT * 0.5), FadeOut(heat_out, shift=LEFT * 0.4),
                      FadeOut(label_plain, shift=DOWN * 0.3), FadeOut(steam_plain),
                      FadeOut(insul_cup, shift=UP * 0.3), FadeOut(label_insul, shift=DOWN * 0.3),
                      FadeOut(steam, shift=UP * 0.3), run_time=0.9, rate_func=rush_into)
            self.play(FadeIn(feature_cup, shift=RIGHT * 0.4), FadeIn(feature_lid, shift=DOWN * 0.3),
                      run_time=1.0, rate_func=smooth)
            self.play(AnimationGroup(*[FadeIn(b, shift=RIGHT * 0.3) for b in bullets], lag_ratio=0.3),
                      run_time=1.6, rate_func=smooth)
            self.play(AnimationGroup(*[Create(d) for d in dashes], lag_ratio=0.25), run_time=1.2)
            self.wait(max(0.1, tracker.duration - 5.2))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="They trap the heat inside, just like they keep the cold in.") as tracker:
            sub = self.show_subtitle("They trap the heat inside, just like they keep the cold in.")
            self.play(FadeOut(dashes, shift=LEFT * 0.2), FadeOut(bullets, shift=RIGHT * 0.3),
                      FadeOut(feature_cup, shift=DOWN * 0.2), FadeOut(feature_lid, shift=UP * 0.4),
                      run_time=0.8, rate_func=rush_into)
            self.play(AnimationGroup(FadeIn(inner_wall, shift=RIGHT * 0.3),
                                     FadeIn(vacuum_gap, shift=RIGHT * 0.5),
                                     FadeIn(outer_wall, shift=RIGHT * 0.7),
                                     lag_ratio=0.25), run_time=1.8, rate_func=smooth)
            explode_lid.move_to(lid_top)
            self.play(FadeIn(explode_lid, shift=UP * 0.3), GrowArrow(gravity_arrow), run_time=0.9)
            self.play(explode_lid.animate.move_to(lid_seat), run_time=0.9, rate_func=smooth)
            self.play(FadeIn(vac_label, shift=LEFT * 0.3), run_time=0.8, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 5.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="We can test this by using cups with and without lids, and with different wall layers.") as tracker:
            sub = self.show_subtitle("We can test this by using cups with and without lids, and with different wall layers.")
            self.play(FadeOut(layers, shift=LEFT * 0.4), FadeOut(explode_lid, shift=UP * 0.4),
                      FadeOut(gravity_arrow, shift=RIGHT * 0.3), FadeOut(vac_label, shift=RIGHT * 0.4),
                      run_time=0.9, rate_func=rush_into)
            self.play(FadeIn(exp_plain, shift=UP * 0.3), FadeIn(exp_insul, shift=UP * 0.3),
                      FadeIn(exp_lid, shift=DOWN * 0.2), FadeIn(exp_label_p), FadeIn(exp_label_i),
                      run_time=1.1, rate_func=smooth)
            self.play(FadeIn(thermo_p), FadeIn(thermo_i), run_time=0.6, rate_func=smooth)
            self.play(AnimationGroup(thermo_p.animate.move_to(thermo_p_target),
                                     thermo_i.animate.move_to(thermo_i_target),
                                     lag_ratio=0.25), run_time=1.1, rate_func=smooth)
            self.play(FadeIn(start_label, shift=DOWN * 0.2), run_time=0.8, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 5.2))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Which one keeps the drink hot longer?") as tracker:
            sub = self.show_subtitle("Which one keeps the drink hot longer?")
            self.play(FadeOut(start_label, shift=UP * 0.3), run_time=0.5, rate_func=rush_into)
            self.play(FadeIn(num_p), FadeIn(num_i), FadeIn(clock_num), run_time=0.5, rate_func=smooth)
            self.play(FadeIn(unit_p), FadeIn(unit_i), FadeIn(clock_label), run_time=0.6, rate_func=smooth)
            self.play(AnimationGroup(*[GrowArrow(a) for a in exp_heat_out], lag_ratio=0.25), run_time=1.0)
            self.play(t_tracker.animate.set_value(60), temp_p.animate.set_value(42.0),
                      temp_i.animate.set_value(84.0), run_time=3.2, rate_func=linear)
            self.wait(max(0.1, tracker.duration - 5.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="The answer is yes!") as tracker:
            sub = self.show_subtitle("The answer is yes!")
            num_p.clear_updaters()
            num_i.clear_updaters()
            clock_num.clear_updaters()
            self.play(FadeOut(num_p, shift=DOWN * 0.2), FadeOut(num_i, shift=DOWN * 0.2),
                      FadeOut(unit_p), FadeOut(unit_i), FadeOut(clock_num), FadeOut(clock_label),
                      FadeOut(exp_heat_out, shift=LEFT * 0.2), FadeOut(thermo_p), FadeOut(thermo_i),
                      run_time=0.8, rate_func=rush_into)
            self.play(FadeIn(res_plain_num), FadeIn(res_plain_unit),
                      FadeIn(res_insul_num), FadeIn(res_insul_unit), run_time=0.8, rate_func=smooth)
            self.play(Circumscribe(insul_group, color=ACCENT, buff=0.25), run_time=1.2)
            self.play(Flash(res_insul_num, color=ACCENT, line_length=0.4), run_time=0.6)
            self.play(FadeIn(delta_tex, shift=UP * 0.2), exp_plain.animate.set_opacity(0.35),
                      run_time=1.0, rate_func=smooth)
            self.play(Indicate(delta_tex, color=ACCENT), run_time=0.7)
            self.wait(max(0.1, tracker.duration - 5.3))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Cups that keep drinks cold can also keep them hot, thanks to their special features.") as tracker:
            sub = self.show_subtitle("Cups that keep drinks cold can also keep them hot, thanks to their special features.")
            self.play(FadeOut(exp_plain, shift=DOWN * 0.5), FadeOut(exp_label_p, shift=DOWN * 0.5),
                      FadeOut(res_plain_num, shift=DOWN * 0.4), FadeOut(res_plain_unit, shift=DOWN * 0.4),
                      FadeOut(res_insul_num, shift=UP * 0.3), FadeOut(res_insul_unit, shift=UP * 0.3),
                      FadeOut(exp_insul, shift=DOWN * 0.3), FadeOut(exp_lid, shift=DOWN * 0.3),
                      FadeOut(exp_label_i, shift=DOWN * 0.4), FadeOut(delta_tex, shift=DOWN * 0.4),
                      run_time=0.9, rate_func=rush_into)
            self.play(FadeIn(hero_cup, shift=UP * 0.2), FadeIn(hero_lid, shift=DOWN * 0.2),
                      run_time=0.9, rate_func=smooth)
            self.play(Circumscribe(hero_lid, color=ACCENT), run_time=0.9)
            self.play(AnimationGroup(GrowArrow(blocked_arrow), GrowArrow(blocked_arrow2), lag_ratio=0.25),
                      run_time=1.0)
            self.play(FadeIn(cross_group, scale=1.4), FadeIn(stopped_label, shift=DOWN * 0.2),
                      run_time=0.8, rate_func=smooth)
            self.play(FadeIn(thermo_hero), FadeIn(hero_num), FadeIn(hero_unit), run_time=0.7, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 5.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So next time you choose a cup, remember: it's not just about keeping things cold.") as tracker:
            sub = self.show_subtitle("So next time you choose a cup, remember: it's not just about keeping things cold.")
            self.play(FadeOut(blocked_group, shift=DOWN * 0.4), FadeOut(cross_group, shift=DOWN * 0.4),
                      FadeOut(stopped_label, shift=UP * 0.3), run_time=0.9, rate_func=rush_into)
            self.play(question.animate.scale(1.5).move_to(UP * 2.4), run_time=1.0, rate_func=smooth)
            self.play(FadeIn(answer, shift=UP * 0.3), run_time=1.2, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 3.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="It's about keeping them just right!") as tracker:
            sub = self.show_subtitle("It's about keeping them just right!")
            self.play(FadeOut(question, shift=UP * 0.3), FadeOut(answer, shift=DOWN * 0.3),
                      FadeOut(hero_cup), FadeOut(hero_lid), FadeOut(thermo_hero),
                      FadeOut(hero_num), FadeOut(hero_unit), run_time=0.8, rate_func=rush_into)
            self.play(FadeIn(final_cup, shift=UP * 0.2), FadeIn(final_lid, shift=DOWN * 0.2),
                      FadeIn(thermo_final), FadeIn(final_num), FadeIn(final_unit),
                      FadeIn(final_caption, shift=UP * 0.2), run_time=1.0, rate_func=smooth)
            self.play(final_cup.animate.scale(1.05), run_time=0.8, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 3.0))
            self.play(FadeOut(final_cup), FadeOut(final_lid), FadeOut(thermo_final),
                      FadeOut(final_num), FadeOut(final_unit), FadeOut(final_caption),
                      FadeOut(sub), run_time=1.0, rate_func=smooth)