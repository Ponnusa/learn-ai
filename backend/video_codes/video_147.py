from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.azure import AzureService
import numpy as np

import base64 as _b64_svg, os as _os

_SVG_DATA = {
    "thermometer": "PHN2ZyB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8Y2lyY2xlIGN4PSI1MCIgY3k9IjgwIiByPSIxMCIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyLjUiLz4KICA8cGF0aCBkPSJNIDQ0IDcwIEwgNDQgMjAgUSA0NCAxNSA1MCAxNSBRIDU2IDE1IDU2IDIwIEwgNTYgNzAiIHN0cm9rZT0id2hpdGUiIGZpbGw9Im5vbmUiIHN0cm9rZS13aWR0aD0iMi41Ii8+CiAgPGxpbmUgeDE9IjQ0IiB5MT0iNzAiIHgyPSI1NiIgeTI9IjcwIiBzdHJva2U9IndoaXRlIiBmaWxsPSJub25lIiBzdHJva2Utd2lkdGg9IjIuNSIvPgogIDxsaW5lIHgxPSI0NiIgeTE9IjQ1IiB4Mj0iNTQiIHkyPSI0NSIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyLjUiLz4KICA8bGluZSB4MT0iNDYiIHkxPSIzNSIgeDI9IjUyIiB5Mj0iMzUiIHN0cm9rZT0id2hpdGUiIGZpbGw9Im5vbmUiIHN0cm9rZS13aWR0aD0iMiIvPgogIDxsaW5lIHgxPSI0NiIgeTE9IjU1IiB4Mj0iNTIiIHkyPSI1NSIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyIi8+Cjwvc3ZnPg==",
    "beaker": "PHN2ZyB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiBzdHJva2U9IndoaXRlIiBmaWxsPSJub25lIiBzdHJva2Utd2lkdGg9IjIuNSI+CiAgPCEtLSBCZWFrZXIgYm9keTogdHJhcGV6b2lkIHdpZGVyIGF0IHRvcCAtLT4KICA8cGF0aCBkPSJNIDIwIDE1IEwgODAgMTUgTCA3MCA4OCBMIDMwIDg4IFoiIHN0cm9rZT0id2hpdGUiIGZpbGw9Im5vbmUiLz4KICA8IS0tIFNwb3V0IGF0IHRvcCBsZWZ0IC0tPgogIDxwYXRoIGQ9Ik0gMjAgMTUgTCAxMiA4IEwgMjIgOCBMIDI4IDE1IiBzdHJva2U9IndoaXRlIiBmaWxsPSJub25lIi8+CiAgPCEtLSBMaXF1aWQgZmlsbCBsaW5lIGluc2lkZSBiZWFrZXIgLS0+CiAgPGxpbmUgeDE9IjMzIiB5MT0iNjUiIHgyPSI2NyIgeTI9IjY1IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiLz4KICA8IS0tIE1lYXN1cmVtZW50IGxpbmVzIG9uIHJpZ2h0IHNpZGUgLS0+CiAgPGxpbmUgeDE9IjY2IiB5MT0iNzUiIHgyPSI3MiIgeTI9Ijc1IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjEuNSIvPgogIDxsaW5lIHgxPSI2NyIgeTE9IjY1IiB4Mj0iNzMiIHkyPSI2NSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIxLjUiLz4KICA8bGluZSB4MT0iNjUiIHkxPSI1NSIgeDI9IjcxIiB5Mj0iNTUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMS41Ii8+CiAgPGxpbmUgeDE9IjY0IiB5MT0iNDUiIHgyPSI3MCIgeTI9IjQ1IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjEuNSIvPgo8L3N2Zz4=",
    "bunsen_burner": "PHN2ZyB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8cGF0aCBkPSJNNDIgNzggTDQyIDM4IEw1OCAzOCBMNTggNzgiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMyIvPgogIDxwYXRoIGQ9Ik0zMCA3OCBMNzAgNzgiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMyIvPgogIDxwYXRoIGQ9Ik0zMiA4OCBMNjggODgiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMyIvPgogIDxwYXRoIGQ9Ik0zMCA3OCBMMzIgODggTTcwIDc4IEw2OCA4OCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIzIi8+CiAgPHBhdGggZD0iTTU4IDcwIEw3NCA3MCBMNzQgNzYiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMyIvPgogIDxwYXRoIGQ9Ik00MiA1NSBMNTggNTUiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIvPgogIDxwYXRoIGQ9Ik01MCAzOCBDNDAgMzAgMzggMjAgNDQgMTAgQzQ2IDE2IDQ4IDE4IDUwIDE5IEM1MiAxMiA1NiA4IDU4IDYgQzYwIDE2IDY0IDI0IDYwIDMyIEM1OCAzNSA1NCAzNyA1MCAzOCBaIiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjMiLz4KPC9zdmc+"
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




class WhyHotChocolateCools(VoiceoverScene):
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
        self.camera.background_color = ManimColor("#0E1420")

        # ═══ SETUP BLOCK: define every object used across the whole scene ═══
        HOT = ORANGE
        COLD = BLUE_D

        def make_dots(n, color, center, spread, radius=0.06):
            return VGroup(*[
                Dot(radius=radius, color=color).move_to(
                    center + np.array([np.random.uniform(-spread, spread),
                                        np.random.uniform(-spread, spread), 0]))
                for _ in range(n)
            ])

        def make_arrows(n, center, length, color, spread=0.3):
            grp = VGroup()
            for _ in range(n):
                angle = np.random.uniform(0, TAU)
                start = center + np.array([np.random.uniform(-spread, spread),
                                            np.random.uniform(-spread, spread), 0])
                end = start + length * np.array([np.cos(angle), np.sin(angle), 0])
                grp.add(Arrow(start, end, buff=0, stroke_width=3, color=color,
                               max_tip_length_to_length_ratio=0.35))
            return grp

        background = Rectangle(width=14.3, height=8.3, stroke_width=0,
                                fill_color=self.camera.background_color, fill_opacity=1)

        title = Text("Why Does Hot Chocolate Cool Down?", font_size=32, color=WHITE).to_edge(UP, buff=0.4)

        students = VGroup(*[
            VGroup(Circle(radius=0.22, color=WHITE, fill_color=BLUE_E, fill_opacity=0.9),
                   Dot(radius=0.03, color=WHITE)).move_to(pos)
            for pos in [LEFT * 4.5 + DOWN * 2.3, LEFT * 1.7 + DOWN * 2.5,
                        RIGHT * 1.7 + DOWN * 2.5, RIGHT * 4.5 + DOWN * 2.3]
        ])

        mug = get_svg("beaker", height=1.4).move_to(ORIGIN)
        thermo1 = get_svg("thermometer", height=1.0).next_to(mug, LEFT, buff=0.6)
        steam_curves = VGroup(*[
            ParametricFunction(lambda t, k=k: np.array([0.12 * np.sin(3 * t) + k * 0.25, t, 0]),
                                t_range=[0, 1.2], color=GRAY_B, stroke_width=2)
            .move_to(mug.get_top() + UP * 0.6 + RIGHT * k * 0.25)
            for k in [-1, 0, 1]
        ])
        temp_number = Text("85°C", font_size=28, color=HOT).next_to(thermo1, UP, buff=0.2)

        beat1_group = VGroup(title, students, mug, thermo1, steam_curves, temp_number)

        hot_beaker = get_svg("beaker", height=1.6).move_to(LEFT * 3.3 + DOWN * 0.3)
        hot_liquid = Rectangle(width=0.9, height=0.9, fill_color=HOT, fill_opacity=0.35,
                                stroke_width=0).move_to(hot_beaker.get_center() + DOWN * 0.1)
        hot_dots = make_dots(14, HOT, hot_beaker.get_center() + DOWN * 0.1, 0.4)
        hot_arrows = make_arrows(4, hot_beaker.get_center() + DOWN * 0.1, 0.5, HOT)
        moving_label = Text("Particles move FAST!", font_size=26, color=HOT).to_edge(DOWN, buff=1.1)
        ke_prop = Text("More heat → more motion", font_size=24, color=WHITE).next_to(moving_label, UP, buff=0.25)
        hot_group = VGroup(hot_beaker, hot_liquid, hot_dots, hot_arrows)

        cold_beaker = get_svg("beaker", height=1.6).move_to(RIGHT * 3.3 + DOWN * 0.3)
        cold_liquid = Rectangle(width=0.9, height=0.9, fill_color=COLD, fill_opacity=0.35,
                                 stroke_width=0).move_to(cold_beaker.get_center() + DOWN * 0.1)
        cold_dots = make_dots(14, COLD, cold_beaker.get_center() + DOWN * 0.1, 0.12)
        cold_arrows = make_arrows(4, cold_beaker.get_center() + DOWN * 0.1, 0.15, COLD)
        thermo2 = get_svg("thermometer", height=1.0).next_to(cold_beaker, RIGHT, buff=0.6)
        cold_temp_number = Text("5°C", font_size=28, color=COLD).next_to(thermo2, UP, buff=0.2)
        colder_label = Text("Particles move SLOW...", font_size=26, color=COLD).to_edge(DOWN, buff=1.1)
        cold_group = VGroup(cold_beaker, cold_liquid, cold_dots, cold_arrows)

        room_rect = Rectangle(width=9.5, height=5.0, color=WHITE, stroke_width=2).move_to(ORIGIN)
        bottle_body = Rectangle(width=0.25, height=0.5, color=WHITE, fill_color=GRAY_B, fill_opacity=1)
        bottle_cap = Triangle(color=WHITE, fill_color=GRAY_B, fill_opacity=1).scale(0.1).next_to(bottle_body, UP, buff=0)
        bottle = VGroup(bottle_body, bottle_cap).move_to(LEFT * 3.5)
        room_students = VGroup(*[
            VGroup(Circle(radius=0.2, color=WHITE, fill_color=BLUE_E, fill_opacity=0.9),
                   Dot(radius=0.03, color=WHITE)).move_to(pos)
            for pos in [RIGHT * 3.2 + UP * 1.2, RIGHT * 3.2 + DOWN * 1.2, RIGHT * 3.8]
        ])
        perfume_dots = VGroup(*[Dot(radius=0.05, color=PURPLE_B).move_to(bottle.get_center())
                                for _ in range(24)])
        perfume_targets = [
            room_rect.get_center() + np.array([np.random.uniform(-4.2, 4.2),
                                                np.random.uniform(-2.2, 2.2), 0])
            for _ in range(24)
        ]
        diffusion_arrow = Arrow(bottle.get_center(), bottle.get_center() + RIGHT * 2.2 + UP * 0.3,
                                 color=PURPLE_B, buff=0.1)
        diffusion_label = Text("Diffusion: particles spread out", font_size=24, color=PURPLE_B).to_edge(DOWN, buff=0.9)
        beat4_group = VGroup(room_rect, bottle, room_students, perfume_dots, diffusion_arrow, diffusion_label)

        ke_eq = MathTex(r"KE = \frac{1}{2}mv^2", font_size=48, color=WHITE).move_to(UP * 1.6)
        implication_chain = Text("Higher Temp  →  Higher KE  →  Faster Particles",
                                  font_size=26, color=WHITE).move_to(UP * 0.4)
        slow_dot = Dot(radius=0.1, color=COLD).move_to(LEFT * 2.5 + DOWN * 1.3)
        fast_dot = Dot(radius=0.1, color=HOT).move_to(RIGHT * 1.0 + DOWN * 1.3)
        slow_arrow = Arrow(slow_dot.get_center(), slow_dot.get_center() + RIGHT * 0.4, color=COLD, buff=0.05)
        fast_arrow = Arrow(fast_dot.get_center(), fast_dot.get_center() + RIGHT * 1.4, color=HOT, buff=0.05)
        slow_lbl = Text("slow", font_size=22, color=COLD).next_to(slow_dot, DOWN, buff=0.25)
        fast_lbl = Text("fast", font_size=22, color=HOT).next_to(fast_dot, DOWN, buff=0.25)
        ke_box = SurroundingRectangle(ke_eq, color=GOLD_A, buff=0.25)
        beat5_group = VGroup(ke_eq, implication_chain, slow_arrow, fast_arrow, slow_dot, fast_dot,
                              slow_lbl, fast_lbl, ke_box)

        center_beaker = get_svg("beaker", height=1.6).move_to(UP * 0.6)
        center_liquid = Rectangle(width=0.9, height=0.9, fill_color=HOT, fill_opacity=0.3,
                                   stroke_width=0).move_to(center_beaker.get_center() + DOWN * 0.1)
        center_dots = make_dots(14, HOT, center_beaker.get_center() + DOWN * 0.1, 0.35)
        burner = get_svg("bunsen_burner", height=1.3).next_to(center_beaker, DOWN, buff=0.05)
        flame_accent = Circle(radius=0.12, color=ORANGE, fill_color=YELLOW, fill_opacity=0.7,
                               stroke_width=0).move_to(burner.get_top() + UP * 0.05)
        heat_arrows = make_arrows(3, burner.get_top(), 0.5, ORANGE, spread=0.15)
        heat_label = Text("Heat energy speeds up particles", font_size=24, color=ORANGE).to_edge(DOWN, buff=0.9)
        beat6_group = VGroup(center_beaker, center_liquid, center_dots, burner, flame_accent,
                              heat_arrows, heat_label)

        res_hot_icon = get_svg("beaker", height=1.2).move_to(RIGHT * 3.0 + UP * 0.3)
        res_hot_dots = make_dots(12, HOT, res_hot_icon.get_center() + DOWN * 0.1, 0.35, radius=0.05)
        res_hot_group = VGroup(res_hot_icon, res_hot_dots)
        res_cold_icon = get_svg("beaker", height=1.2).move_to(LEFT * 3.0 + UP * 0.3)
        res_cold_dots = make_dots(12, COLD, res_cold_icon.get_center() + DOWN * 0.1, 0.1, radius=0.05)
        res_cold_group = VGroup(res_cold_icon, res_cold_dots)
        hot_res_tracker = ValueTracker(0.0)
        cold_res_tracker = ValueTracker(0.0)
        hot_res_num = DecimalNumber(0, num_decimal_places=0, color=HOT, font_size=28).next_to(res_hot_icon, DOWN, buff=0.3)
        hot_res_num.add_updater(lambda m: m.set_value(hot_res_tracker.get_value()))
        cold_res_num = DecimalNumber(0, num_decimal_places=0, color=COLD, font_size=28).next_to(res_cold_icon, DOWN, buff=0.3)
        cold_res_num.add_updater(lambda m: m.set_value(cold_res_tracker.get_value()))
        result_caption = Text("Speed reflects temperature!", font_size=24, color=WHITE).to_edge(DOWN, buff=0.9)

        final_mug = get_svg("beaker", height=1.5).move_to(ORIGIN)
        final_dots = make_dots(14, HOT, final_mug.get_center() + DOWN * 0.1, 0.35)
        final_thermo = get_svg("thermometer", height=1.0).next_to(final_mug, LEFT, buff=0.6)
        final_temp_tracker = ValueTracker(85.0)
        final_temp_num = DecimalNumber(85, num_decimal_places=0, color=HOT, font_size=28).next_to(final_thermo, UP, buff=0.2)
        final_temp_num.add_updater(lambda m: m.set_value(final_temp_tracker.get_value()))
        final_steam = VGroup(*[
            ParametricFunction(lambda t, k=k: np.array([0.12 * np.sin(3 * t) + k * 0.25, t, 0]),
                                t_range=[0, 1.2], color=GRAY_B, stroke_width=2)
            .move_to(final_mug.get_top() + UP * 0.6 + RIGHT * k * 0.25)
            for k in [-1, 0, 1]
        ])
        final_line = Text("It's all about particles slowing down!", font_size=26, color=WHITE).to_edge(DOWN, buff=0.8)

        self.add(background)
        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Have you ever wondered why your hot chocolate cools down or why you can smell perfume from across the room?") as tracker:
            sub = self.show_subtitle("Have you ever wondered why your hot chocolate cools down or why you can smell perfume from across the room?")
            self.play(FadeIn(title, shift=DOWN * 0.5), run_time=1.4, rate_func=smooth)
            self.play(AnimationGroup(*[FadeIn(s, shift=UP * 0.4) for s in students], lag_ratio=0.3),
                      run_time=1.6, rate_func=smooth)
            self.play(DrawBorderThenFill(mug), run_time=1.4, rate_func=smooth)
            self.play(FadeIn(thermo1, shift=LEFT * 0.5), Create(steam_curves), run_time=1.8, rate_func=smooth)
            self.play(FadeIn(temp_number, shift=UP * 0.2), run_time=0.9, rate_func=smooth)
            self.play(steam_curves.animate.shift(UP * 0.25), run_time=1.2, rate_func=linear)
            self.wait(max(0.1, tracker.duration - 8.8))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Let's dive into the world of particles! Imagine particles in a hot liquid. They move fast, like tiny race cars zooming around.") as tracker:
            sub = self.show_subtitle("Let's dive into the world of particles! Imagine particles in a hot liquid. They move fast, like tiny race cars zooming around.")
            self.play(FadeOut(beat1_group, shift=LEFT * 0.5), run_time=0.9, rate_func=rush_into)
            self.play(FadeIn(hot_beaker, shift=UP * 0.3), FadeIn(hot_liquid), run_time=1.2, rate_func=smooth)
            self.play(AnimationGroup(*[FadeIn(d, scale=0.4) for d in hot_dots], lag_ratio=0.2),
                      run_time=1.8, rate_func=smooth)
            self.play(AnimationGroup(*[GrowArrow(a) for a in hot_arrows], lag_ratio=0.25),
                      run_time=1.4, rate_func=smooth)
            self.play(FadeIn(moving_label, shift=UP * 0.2), run_time=1.0, rate_func=smooth)
            self.play(FadeIn(ke_prop, shift=UP * 0.2), run_time=0.9, rate_func=smooth)
            shifts = [np.array([np.random.uniform(-0.24, 0.24), np.random.uniform(-0.2, 0.2), 0]) for _ in range(14)]
            self.play(*[hot_dots[i].animate.shift(shifts[i]) for i in range(14)],
                      *[hot_arrows[i].animate.shift(shifts[i]) for i in range(4)],
                      run_time=1.4, rate_func=there_and_back)
            self.wait(max(0.1, tracker.duration - 9.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Now, picture them in a cold liquid. They slow down, like cars in a traffic jam.") as tracker:
            sub = self.show_subtitle("Now, picture them in a cold liquid. They slow down, like cars in a traffic jam.")
            self.play(FadeOut(moving_label, shift=UP * 0.3), FadeOut(ke_prop, shift=UP * 0.3),
                      run_time=0.7, rate_func=rush_into)
            self.play(FadeIn(cold_beaker, shift=LEFT * 0.4), FadeIn(cold_liquid), run_time=1.0, rate_func=smooth)
            self.play(AnimationGroup(*[FadeIn(d, scale=0.5) for d in cold_dots], lag_ratio=0.18),
                      run_time=1.6, rate_func=smooth)
            self.play(AnimationGroup(*[GrowArrow(a) for a in cold_arrows], lag_ratio=0.2),
                      run_time=1.2, rate_func=smooth)
            self.play(FadeIn(thermo2, shift=DOWN * 0.3), FadeIn(cold_temp_number), run_time=0.9, rate_func=smooth)
            self.play(FadeIn(colder_label, shift=UP * 0.2), run_time=0.9, rate_func=smooth)
            cshifts = [np.array([np.random.uniform(-0.05, 0.05), np.random.uniform(-0.05, 0.05), 0]) for _ in range(14)]
            hshifts = [np.array([np.random.uniform(-0.24, 0.24), np.random.uniform(-0.2, 0.2), 0]) for _ in range(14)]
            self.play(*[cold_dots[i].animate.shift(cshifts[i]) for i in range(14)],
                      *[cold_arrows[i].animate.shift(cshifts[i]) for i in range(4)],
                      *[hot_dots[i].animate.shift(hshifts[i]) for i in range(14)],
                      *[hot_arrows[i].animate.shift(hshifts[i]) for i in range(4)],
                      run_time=1.6, rate_func=there_and_back)
            self.wait(max(0.1, tracker.duration - 8.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="When you spray perfume, the scent spreads because gas particles move freely, just like in liquids.") as tracker:
            sub = self.show_subtitle("When you spray perfume, the scent spreads because gas particles move freely, just like in liquids.")
            self.play(FadeOut(hot_group, shift=LEFT * 0.5), FadeOut(cold_group, shift=RIGHT * 0.5),
                      FadeOut(colder_label), FadeOut(cold_temp_number), FadeOut(thermo2), run_time=1.0, rate_func=rush_into)
            self.play(Create(room_rect), run_time=1.1, rate_func=smooth)
            self.play(DrawBorderThenFill(bottle), FadeIn(room_students), run_time=1.1, rate_func=smooth)
            self.play(FadeIn(perfume_dots, scale=0.5), run_time=0.6, rate_func=smooth)
            self.play(AnimationGroup(*[perfume_dots[i].animate.move_to(perfume_targets[i]) for i in range(24)],
                                     lag_ratio=0.12), run_time=3.2, rate_func=rush_from)
            self.play(GrowArrow(diffusion_arrow), run_time=1.0, rate_func=smooth)
            self.play(FadeIn(diffusion_label, shift=DOWN * 0.2), run_time=1.0, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 8.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="This movement is called kinetic energy. The hotter it is, the more energy particles have, and the faster they move.") as tracker:
            sub = self.show_subtitle("This movement is called kinetic energy. The hotter it is, the more energy particles have, and the faster they move.")
            self.play(FadeOut(beat4_group, shift=DOWN * 0.4), run_time=1.0, rate_func=rush_into)
            self.play(Write(ke_eq), run_time=2.0)
            self.play(Indicate(ke_eq, color=GOLD_A), run_time=1.0)
            self.play(FadeIn(implication_chain, shift=UP * 0.2), run_time=1.4, rate_func=smooth)
            self.play(AnimationGroup(GrowArrow(slow_arrow), GrowArrow(fast_arrow), lag_ratio=0.25),
                      FadeIn(slow_dot), FadeIn(fast_dot), FadeIn(slow_lbl), FadeIn(fast_lbl),
                      run_time=1.4, rate_func=smooth)
            self.play(Create(ke_box), run_time=1.1, rate_func=smooth)
            self.play(slow_dot.animate.shift(RIGHT * 0.15), slow_arrow.animate.shift(RIGHT * 0.15),
                      fast_dot.animate.shift(RIGHT * 0.6), fast_arrow.animate.shift(RIGHT * 0.6),
                      run_time=1.3, rate_func=there_and_back)
            self.wait(max(0.1, tracker.duration - 8.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So, temperature is like a speed dial for particles.") as tracker:
            sub = self.show_subtitle("So, temperature is like a speed dial for particles.")
            self.play(FadeOut(beat5_group, shift=LEFT * 0.5), run_time=0.9, rate_func=rush_into)
            self.play(FadeIn(center_beaker, shift=UP * 0.3), FadeIn(center_liquid), FadeIn(center_dots),
                      run_time=1.2, rate_func=smooth)
            self.play(FadeIn(burner, shift=UP * 0.4), FadeIn(flame_accent), run_time=1.0, rate_func=smooth)
            self.play(AnimationGroup(*[GrowArrow(a) for a in heat_arrows], lag_ratio=0.2),
                      run_time=1.2, rate_func=smooth)
            self.play(Indicate(burner, scale_factor=1.3, color=HOT), run_time=1.0)
            self.play(Circumscribe(center_beaker, color=GOLD_A, buff=0.15), run_time=1.4)
            self.play(FadeIn(heat_label, shift=LEFT * 0.2), run_time=0.9, rate_func=smooth)
            mshifts = [np.array([np.random.uniform(-0.3, 0.3), np.random.uniform(-0.25, 0.25), 0]) for _ in range(14)]
            self.play(*[center_dots[i].animate.shift(mshifts[i]) for i in range(14)],
                      run_time=1.3, rate_func=there_and_back)
            self.wait(max(0.1, tracker.duration - 9.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Hot liquids and gases have fast-moving particles, while cold ones have slow-moving particles.") as tracker:
            sub = self.show_subtitle("Hot liquids and gases have fast-moving particles, while cold ones have slow-moving particles.")
            self.play(FadeOut(beat6_group, shift=DOWN * 0.4), run_time=1.0, rate_func=rush_into)
            self.play(FadeIn(res_hot_group, shift=RIGHT * 0.4), FadeIn(res_cold_group, shift=LEFT * 0.4),
                      run_time=1.3, rate_func=smooth)
            self.play(FadeIn(hot_res_num), FadeIn(cold_res_num), run_time=0.7, rate_func=smooth)
            self.play(hot_res_tracker.animate.set_value(90.0), cold_res_tracker.animate.set_value(5.0),
                      run_time=1.6, rate_func=smooth)
            self.play(Circumscribe(res_hot_group, color=HOT, buff=0.12), run_time=1.2)
            self.play(Circumscribe(res_cold_group, color=COLD, buff=0.12), run_time=1.2)
            rshifts = [np.array([np.random.uniform(-0.26, 0.26), np.random.uniform(-0.2, 0.2), 0]) for _ in range(12)]
            kshifts = [np.array([np.random.uniform(-0.05, 0.05), np.random.uniform(-0.05, 0.05), 0]) for _ in range(12)]
            self.play(*[res_hot_dots[i].animate.shift(rshifts[i]) for i in range(12)],
                      *[res_cold_dots[i].animate.shift(kshifts[i]) for i in range(12)],
                      FadeIn(result_caption, shift=UP * 0.2), run_time=1.4, rate_func=there_and_back)
            self.wait(max(0.1, tracker.duration - 8.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Next time you sip hot chocolate, remember, it's all about those speedy particles slowing down!") as tracker:
            sub = self.show_subtitle("Next time you sip hot chocolate, remember, it's all about those speedy particles slowing down!")
            self.play(FadeOut(res_hot_group, shift=LEFT * 0.4), FadeOut(res_cold_group, shift=RIGHT * 0.4),
                      FadeOut(hot_res_num), FadeOut(cold_res_num), FadeOut(result_caption),
                      run_time=1.1, rate_func=rush_into)
            self.play(FadeIn(final_mug, shift=UP * 0.3), FadeIn(final_dots), FadeIn(final_thermo, shift=LEFT * 0.3),
                      FadeIn(final_temp_num), run_time=1.3, rate_func=smooth)
            self.play(Create(final_steam), run_time=1.0, rate_func=smooth)
            self.play(final_temp_tracker.animate.set_value(25.0),
                      *[d.animate.set_color(ManimColor("#8FC7FF")) for d in final_dots],
                      final_temp_num.animate.set_color(COLD),
                      FadeOut(final_steam, shift=UP * 0.4), run_time=2.4, rate_func=smooth)
            self.play(FadeIn(final_line, shift=DOWN * 0.2), run_time=1.2, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 8.0))
            self.play(FadeOut(sub), run_time=0.4)

        self.play(FadeOut(final_mug), FadeOut(final_dots), FadeOut(final_thermo),
                  FadeOut(final_temp_num), FadeOut(final_line), run_time=1.6, rate_func=linear)