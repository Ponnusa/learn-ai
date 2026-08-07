from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.azure import AzureService
import numpy as np

import base64 as _b64_svg, os as _os

_SVG_DATA = {
    "thermometer": "PHN2ZyB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8Y2lyY2xlIGN4PSI1MCIgY3k9IjgwIiByPSIxMCIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyLjUiLz4KICA8cGF0aCBkPSJNIDQ0IDcwIEwgNDQgMjAgUSA0NCAxNSA1MCAxNSBRIDU2IDE1IDU2IDIwIEwgNTYgNzAiIHN0cm9rZT0id2hpdGUiIGZpbGw9Im5vbmUiIHN0cm9rZS13aWR0aD0iMi41Ii8+CiAgPGxpbmUgeDE9IjQ0IiB5MT0iNzAiIHgyPSI1NiIgeTI9IjcwIiBzdHJva2U9IndoaXRlIiBmaWxsPSJub25lIiBzdHJva2Utd2lkdGg9IjIuNSIvPgogIDxsaW5lIHgxPSI0NiIgeTE9IjQ1IiB4Mj0iNTQiIHkyPSI0NSIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyLjUiLz4KICA8bGluZSB4MT0iNDYiIHkxPSIzNSIgeDI9IjUyIiB5Mj0iMzUiIHN0cm9rZT0id2hpdGUiIGZpbGw9Im5vbmUiIHN0cm9rZS13aWR0aD0iMiIvPgogIDxsaW5lIHgxPSI0NiIgeTE9IjU1IiB4Mj0iNTIiIHkyPSI1NSIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyIi8+Cjwvc3ZnPg==",
    "sun_star": "PHN2ZyB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiBzdHJva2U9IndoaXRlIiBmaWxsPSJub25lIiBzdHJva2Utd2lkdGg9IjIuNSI+CiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgcj0iMTUiLz4KICA8bGluZSB4MT0iNTAiIHkxPSIyOCIgeDI9IjUwIiB5Mj0iMjAiLz4KICA8bGluZSB4MT0iNTAiIHkxPSI3MiIgeDI9IjUwIiB5Mj0iODAiLz4KICA8bGluZSB4MT0iMjgiIHkxPSI1MCIgeDI9IjIwIiB5Mj0iNTAiLz4KICA8bGluZSB4MT0iNzIiIHkxPSI1MCIgeDI9IjgwIiB5Mj0iNTAiLz4KICA8bGluZSB4MT0iMzQuNCIgeTE9IjM0LjQiIHgyPSIyOC44IiB5Mj0iMjguOCIvPgogIDxsaW5lIHgxPSI2NS42IiB5MT0iNjUuNiIgeDI9IjcxLjIiIHkyPSI3MS4yIi8+CiAgPGxpbmUgeDE9IjY1LjYiIHkxPSIzNC40IiB4Mj0iNzEuMiIgeTI9IjI4LjgiLz4KICA8bGluZSB4MT0iMzQuNCIgeTE9IjY1LjYiIHgyPSIyOC44IiB5Mj0iNzEuMiIvPgo8L3N2Zz4=",
    "light_bulb": "PHN2ZyB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiBzdHJva2U9IndoaXRlIiBmaWxsPSJub25lIiBzdHJva2Utd2lkdGg9IjIuNSI+CiAgPCEtLSBHbGFzcyBnbG9iZSAtLT4KICA8Y2lyY2xlIGN4PSI1MCIgY3k9IjQ1IiByPSIyOCIvPgogIDwhLS0gQ29udGFjdCBsaW5lcyBhdCBib3R0b20gLS0+CiAgPGxpbmUgeDE9IjQzIiB5MT0iNzMiIHgyPSI0MyIgeTI9IjgzIi8+CiAgPGxpbmUgeDE9IjU3IiB5MT0iNzMiIHgyPSI1NyIgeTI9IjgzIi8+CiAgPCEtLSBCYXNlIGNvbm5lY3RvciAtLT4KICA8bGluZSB4MT0iNDMiIHkxPSI4MyIgeDI9IjU3IiB5Mj0iODMiLz4KICA8bGluZSB4MT0iNDMiIHkxPSI3MyIgeDI9IjU3IiB5Mj0iNzMiLz4KICA8IS0tIEZpbGFtZW50IGNvaWwgaW5zaWRlIC0tPgogIDxwYXRoIGQ9Ik0gMzggNTAgUSA0MSA0NCA0NCA1MCBRIDQ3IDU2IDUwIDUwIFEgNTMgNDQgNTYgNTAgUSA1OSA1NiA2MiA1MCIgc3Ryb2tlLXdpZHRoPSIyIi8+CiAgPCEtLSBGaWxhbWVudCBsZWdzIC0tPgogIDxsaW5lIHgxPSIzOCIgeTE9IjUwIiB4Mj0iMzgiIHkyPSI2MCIvPgogIDxsaW5lIHgxPSI2MiIgeTE9IjUwIiB4Mj0iNjIiIHkyPSI2MCIvPgogIDxsaW5lIHgxPSIzOCIgeTE9IjYwIiB4Mj0iNjIiIHkyPSI2MCIvPgo8L3N2Zz4=",
    "beaker": "PHN2ZyB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiBzdHJva2U9IndoaXRlIiBmaWxsPSJub25lIiBzdHJva2Utd2lkdGg9IjIuNSI+CiAgPCEtLSBCZWFrZXIgYm9keTogdHJhcGV6b2lkIHdpZGVyIGF0IHRvcCAtLT4KICA8cGF0aCBkPSJNIDIwIDE1IEwgODAgMTUgTCA3MCA4OCBMIDMwIDg4IFoiIHN0cm9rZT0id2hpdGUiIGZpbGw9Im5vbmUiLz4KICA8IS0tIFNwb3V0IGF0IHRvcCBsZWZ0IC0tPgogIDxwYXRoIGQ9Ik0gMjAgMTUgTCAxMiA4IEwgMjIgOCBMIDI4IDE1IiBzdHJva2U9IndoaXRlIiBmaWxsPSJub25lIi8+CiAgPCEtLSBMaXF1aWQgZmlsbCBsaW5lIGluc2lkZSBiZWFrZXIgLS0+CiAgPGxpbmUgeDE9IjMzIiB5MT0iNjUiIHgyPSI2NyIgeTI9IjY1IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiLz4KICA8IS0tIE1lYXN1cmVtZW50IGxpbmVzIG9uIHJpZ2h0IHNpZGUgLS0+CiAgPGxpbmUgeDE9IjY2IiB5MT0iNzUiIHgyPSI3MiIgeTI9Ijc1IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjEuNSIvPgogIDxsaW5lIHgxPSI2NyIgeTE9IjY1IiB4Mj0iNzMiIHkyPSI2NSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIxLjUiLz4KICA8bGluZSB4MT0iNjUiIHkxPSI1NSIgeDI9IjcxIiB5Mj0iNTUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMS41Ii8+CiAgPGxpbmUgeDE9IjY0IiB5MT0iNDUiIHgyPSI3MCIgeTI9IjQ1IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjEuNSIvPgo8L3N2Zz4="
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




class WhyDarkCupsHeatFaster(VoiceoverScene):
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

        # ═══════════════════ SETUP BLOCK ═══════════════════
        title = Text("Why Do Dark Cups Heat Faster?", font_size=32, color=WHITE).to_edge(UP, buff=0.4)

        cup_colors = [ManimColor("#1B1B1B"), ManimColor("#9E9E9E"), ManimColor("#F5F5F5")]
        cup_names = ["Black", "Gray", "White"]

        cupA = get_svg("beaker", height=1.6).set_color(cup_colors[0]).move_to(np.array([-4.0, -0.4, 0]))
        cupB = get_svg("beaker", height=1.6).set_color(cup_colors[1]).move_to(np.array([0.0, -0.4, 0]))
        cupC = get_svg("beaker", height=1.6).set_color(cup_colors[2]).move_to(np.array([4.0, -0.4, 0]))

        waterA = Rectangle(width=0.9, height=0.7, fill_color=ManimColor("#3FA9F5"),
                            fill_opacity=0.55, stroke_width=0).move_to(cupA.get_center() + DOWN * 0.15)
        waterB = Rectangle(width=0.9, height=0.7, fill_color=ManimColor("#3FA9F5"),
                            fill_opacity=0.55, stroke_width=0).move_to(cupB.get_center() + DOWN * 0.15)
        waterC = Rectangle(width=0.9, height=0.7, fill_color=ManimColor("#3FA9F5"),
                            fill_opacity=0.55, stroke_width=0).move_to(cupC.get_center() + DOWN * 0.15)
        waters = [waterA, waterB, waterC]

        cup_labels = VGroup(*[
            Text(name, font_size=22, color=WHITE).next_to(cup, DOWN, buff=0.3)
            for name, cup in zip(cup_names, [cupA, cupB, cupC])
        ])

        sun_star = get_svg("sun_star", height=1.0).move_to(np.array([0, 2.5, 0]))
        sun_pos = sun_star.get_center()
        bulb_badge = get_svg("light_bulb", height=0.6).next_to(title, RIGHT, buff=0.4)

        rays = VGroup(*[
            Arrow(sun_star.get_bottom(), cup.get_top(), buff=0.1, color=YELLOW, stroke_width=3)
            for cup in [cupA, cupB, cupC]
        ])

        equal_light = Text("Equal light reaches all cups", font_size=26, color=YELLOW).move_to(np.array([0, 1.9, 0]))

        hero_A = Arrow(sun_star.get_bottom(), cupA.get_top(), buff=0.1, color=YELLOW, stroke_width=3)
        hero_B = Arrow(sun_star.get_bottom(), cupB.get_top(), buff=0.1, color=YELLOW, stroke_width=3)
        hero_C = Arrow(sun_star.get_bottom(), cupC.get_top(), buff=0.1, color=YELLOW, stroke_width=3)
        hero_rays = VGroup(hero_A, hero_B, hero_C)

        abs_arrow = Arrow(cupA.get_top(), cupA.get_top() + DOWN * 0.8, buff=0.05,
                           color=ManimColor("#FF3B30"), stroke_width=3)
        refl_arrow = Arrow(cupA.get_top(), cupA.get_top() + UP * 0.8 + RIGHT * 0.3, buff=0.05,
                            color=ManimColor("#00E0FF"), stroke_width=3)
        trans_arrow = Arrow(cupA.get_top(), cupA.get_bottom() + DOWN * 0.6, buff=0.05,
                             color=ManimColor("#7CFC00"), stroke_width=3)

        fate_labels = VGroup(
            Text("Absorbed", font_size=18, color=ManimColor("#FF3B30")).next_to(abs_arrow, RIGHT, buff=0.1),
            Text("Reflected", font_size=18, color=ManimColor("#00E0FF")).next_to(refl_arrow, UP, buff=0.1),
            Text("Transmitted", font_size=18, color=ManimColor("#7CFC00")).next_to(trans_arrow, LEFT, buff=0.1),
        )

        heat_dots = VGroup(*[
            Dot(point=cupA.get_center() + np.array([np.random.uniform(-0.3, 0.3),
                                                      np.random.uniform(-0.3, 0.3), 0]),
                radius=0.05, color=ManimColor("#FF7043"))
            for _ in range(8)
        ])

        energy_eq = MathTex(r"E_{absorbed} = E_{incident} - E_{reflected} - E_{transmitted}",
                             font_size=30, color=WHITE).move_to(np.array([0, -2.6, 0]))

        thermA = get_svg("thermometer", height=1.0).next_to(cupA, RIGHT, buff=0.35)
        thermB = get_svg("thermometer", height=1.0).next_to(cupB, RIGHT, buff=0.35)
        thermC = get_svg("thermometer", height=1.0).next_to(cupC, RIGHT, buff=0.35)
        therms = VGroup(thermA, thermB, thermC)

        mercA = Rectangle(width=0.12, height=0.3, fill_color=ManimColor("#3FA9F5"),
                           fill_opacity=1, stroke_width=0).move_to(thermA.get_bottom() + np.array([0, 0.45, 0]))
        mercB = Rectangle(width=0.12, height=0.3, fill_color=ManimColor("#3FA9F5"),
                           fill_opacity=1, stroke_width=0).move_to(thermB.get_bottom() + np.array([0, 0.45, 0]))
        mercC = Rectangle(width=0.12, height=0.3, fill_color=ManimColor("#3FA9F5"),
                           fill_opacity=1, stroke_width=0).move_to(thermC.get_bottom() + np.array([0, 0.45, 0]))
        mercuries = VGroup(mercA, mercB, mercC)

        tA = ValueTracker(22.0)
        tB = ValueTracker(22.0)
        tC = ValueTracker(22.0)

        decA = DecimalNumber(22.0, num_decimal_places=1, font_size=20, color=WHITE).next_to(thermA, UP, buff=0.15)
        decB = DecimalNumber(22.0, num_decimal_places=1, font_size=20, color=WHITE).next_to(thermB, UP, buff=0.15)
        decC = DecimalNumber(22.0, num_decimal_places=1, font_size=20, color=WHITE).next_to(thermC, UP, buff=0.15)
        decA.add_updater(lambda d: d.set_value(tA.get_value()))
        decB.add_updater(lambda d: d.set_value(tB.get_value()))
        decC.add_updater(lambda d: d.set_value(tC.get_value()))
        decimals = VGroup(decA, decB, decC)

        hottest_text = Text("Black absorbs the most → hottest water", font_size=26,
                             color=ManimColor("#FF7043")).move_to(np.array([0, 3.4, 0]))

        scrim = Rectangle(width=14, height=8, fill_color=BLACK, fill_opacity=0.75, stroke_width=0).move_to(ORIGIN)

        no_light_badge = Circle(radius=0.5, color=WHITE, stroke_width=3).move_to(np.array([0, 2.6, 0]))
        _nl_s, _nl_e = no_light_badge.get_corner(UL), no_light_badge.get_corner(DR)
        if np.linalg.norm(_nl_e - _nl_s) > 0.01:
            no_light_slash = Line(_nl_s, _nl_e, color=WHITE, stroke_width=3)
        else:
            no_light_slash = Line(no_light_badge.get_left(), no_light_badge.get_right(), color=WHITE, stroke_width=3)
        no_light_text = Text("No light: water warms slowly", font_size=24, color=WHITE).next_to(
            no_light_badge, DOWN, buff=0.3)
        dark_group = VGroup(no_light_badge, no_light_slash, no_light_text)

        sun_star2 = get_svg("sun_star", height=1.0).move_to(np.array([0, 2.5, 0]))

        chain = VGroup(
            Text("Light", font_size=22, color=YELLOW),
            Text("→", font_size=22, color=WHITE),
            Text("Absorbed by dark surface", font_size=22, color=ManimColor("#FF7043")),
            Text("→", font_size=22, color=WHITE),
            Text("Heat → Warmer Water", font_size=22, color=ManimColor("#FF3B30")),
        ).arrange(RIGHT, buff=0.3).move_to(np.array([0, -3.0, 0]))

        rimB = cupB.get_top()
        mg = Arrow(cupA.get_top(), cupA.get_top() + DOWN * 1.0, buff=0.05,
                   color=ManimColor("#FF7043"), stroke_width=3)
        N = Arrow(cupA.get_top(), cupA.get_top() + UP * 1.0, buff=0.05,
                  color=ManimColor("#3FA9F5"), stroke_width=3)
        E_in_arrow = Arrow(sun_pos + np.array([-0.2, -0.7, 0]), cupA.get_top(), buff=0.1,
                            color=YELLOW, stroke_width=3)
        mg_label = Text("Heat generated", font_size=18, color=ManimColor("#FF7043")).next_to(mg, RIGHT, buff=0.15)
        N_label = Text("Some light reflected", font_size=18, color=ManimColor("#3FA9F5")).next_to(N, RIGHT, buff=0.15)

        heroGroup = VGroup(cupA, waterA, thermA, mercA, decA)

        key_group = VGroup(
            Text("• Dark surfaces absorb more light", font_size=22, color=WHITE),
            Text("• Absorbed light becomes heat", font_size=22, color=WHITE),
            Text("• More heat → faster warming", font_size=22, color=WHITE),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.25).move_to(np.array([-3.2, -1.0, 0]))

        final_text = Text("Dark surfaces absorb more light → water warms fastest",
                           font_size=26, color=ManimColor("#FF7043")).move_to(np.array([0, 3.4, 0]))

        result_text = Text("Result: water warm", font_size=28, color=GOLD).move_to(np.array([0, 1.9, 0]))
        result_box = SurroundingRectangle(result_text, color=GOLD, buff=0.2, stroke_width=3)
        result_group = VGroup(result_text, result_box)
        # ═══════════════════ END SETUP BLOCK ═══════════════════

        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Imagine you have cups made of different materials. Some are shiny, some are dark. What happens when light shines on them?") as tracker:
            sub = self.show_subtitle("Imagine you have cups made of different materials. Some are shiny, some are dark. What happens when light shines on them?")
            self.play(AnimationGroup(FadeIn(cupA, shift=UP * 0.6), FadeIn(cupB, shift=UP * 0.6), FadeIn(cupC, shift=UP * 0.6), lag_ratio=0.30), run_time=2.4, rate_func=smooth)
            self.play(AnimationGroup(*[DrawBorderThenFill(w) for w in waters], lag_ratio=0.25), run_time=1.8, rate_func=smooth)
            self.play(AnimationGroup(*[FadeIn(l, shift=UP * 0.2) for l in cup_labels], lag_ratio=0.3), run_time=1.6, rate_func=smooth)
            self.play(FadeIn(title, shift=DOWN * 0.3), run_time=1.4, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 7.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Let's find out!") as tracker:
            sub = self.show_subtitle("Let's find out!")
            self.play(FadeIn(sun_star, scale=0.4), FadeIn(bulb_badge, shift=RIGHT * 0.2), run_time=1.2, rate_func=smooth)
            self.play(Indicate(sun_star, scale_factor=1.15, color=YELLOW), run_time=0.9)
            self.play(AnimationGroup(*[GrowArrow(r) for r in rays], lag_ratio=0.18), run_time=3.0)
            self.play(FadeIn(equal_light, shift=UP * 0.2), run_time=1.3, rate_func=smooth)
            self.play(LaggedStart(*[Indicate(r, scale_factor=1.05, color=WHITE) for r in rays], lag_ratio=0.12), run_time=1.8)
            self.wait(max(0.1, tracker.duration - 8.2))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="When light hits a cup, it can be absorbed, reflected, or transmitted. But how does this affect the water inside?") as tracker:
            sub = self.show_subtitle("When light hits a cup, it can be absorbed, reflected, or transmitted. But how does this affect the water inside?")
            self.play(rays.animate.set_opacity(0.25), FadeOut(equal_light, shift=UP * 0.3), FadeOut(title, shift=UP * 0.3), FadeOut(bulb_badge, shift=LEFT * 0.3), run_time=1.0, rate_func=rush_into)
            self.play(AnimationGroup(GrowArrow(hero_A), GrowArrow(hero_B), GrowArrow(hero_C), lag_ratio=0.25), run_time=2.2)
            self.play(AnimationGroup(GrowArrow(abs_arrow), GrowArrow(refl_arrow), GrowArrow(trans_arrow), lag_ratio=0.25), run_time=2.6)
            self.play(AnimationGroup(*[FadeIn(l, shift=UP * 0.2) for l in fate_labels], lag_ratio=0.25), run_time=1.8, rate_func=smooth)
            self.play(LaggedStart(*[FadeIn(d, scale=0.3) for d in heat_dots], lag_ratio=0.2), run_time=1.6)
            self.play(FadeIn(energy_eq, shift=DOWN * 0.3), run_time=1.5, rate_func=smooth)
            self.play(Indicate(energy_eq, color=YELLOW, scale_factor=1.08), run_time=0.9)
            self.wait(max(0.1, tracker.duration - 11.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="We discover that water in cups exposed to light warms up more than in the dark. Why? Because the light energy is absorbed by the cup's surface, warming the water.") as tracker:
            sub = self.show_subtitle("We discover that water in cups exposed to light warms up more than in the dark. Why? Because the light energy is absorbed by the cup's surface, warming the water.")
            self.play(FadeOut(fate_labels, shift=UP * 0.3), FadeOut(energy_eq, shift=UP * 0.3), run_time=0.8, rate_func=rush_into)
            self.play(AnimationGroup(*[FadeIn(t, shift=RIGHT * 0.4) for t in therms], lag_ratio=0.25), run_time=1.5, rate_func=smooth)
            self.play(FadeIn(mercuries), FadeIn(decimals), run_time=0.6)
            self.play(tA.animate.set_value(31.4), tB.animate.set_value(26.8), tC.animate.set_value(24.1),
                      mercA.animate.stretch_to_fit_height(1.15).move_to(thermA.get_bottom() + np.array([0, 0.88, 0])),
                      mercB.animate.stretch_to_fit_height(0.70).move_to(thermB.get_bottom() + np.array([0, 0.65, 0])),
                      mercC.animate.stretch_to_fit_height(0.45).move_to(thermC.get_bottom() + np.array([0, 0.52, 0])),
                      waterA.animate.set_fill(ManimColor("#FF7043")),
                      run_time=4.0, rate_func=rush_from)
            self.play(Flash(thermA.get_bottom(), color=ManimColor("#FF3B30"), line_length=0.5, flash_radius=0.8), run_time=0.9)
            self.play(Indicate(decA, scale_factor=1.6, color=ManimColor("#FF3B30")), run_time=0.8)
            self.play(FadeIn(hottest_text, shift=DOWN * 0.3), run_time=1.4, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 11.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Even in the dark, water can warm up, but not as much. This shows that light transfers energy, which can warm things up.") as tracker:
            sub = self.show_subtitle("Even in the dark, water can warm up, but not as much. This shows that light transfers energy, which can warm things up.")
            self.play(FadeOut(sun_star, shift=UP * 1.2), FadeOut(rays, shift=UP * 0.4),
                      FadeOut(hero_rays, shift=UP * 0.4), FadeOut(abs_arrow), FadeOut(refl_arrow),
                      FadeOut(trans_arrow), FadeOut(heat_dots), FadeOut(hottest_text, shift=UP * 0.3),
                      run_time=1.1, rate_func=rush_into)
            self.play(FadeIn(scrim, shift=DOWN * 0.5), run_time=1.4, rate_func=smooth)
            self.play(Create(no_light_badge), Create(no_light_slash), run_time=1.2, rate_func=smooth)
            self.play(FadeIn(no_light_text, shift=DOWN * 0.2), run_time=1.0, rate_func=smooth)
            self.play(tA.animate.set_value(23.0), tB.animate.set_value(22.6), tC.animate.set_value(22.4),
                      mercA.animate.stretch_to_fit_height(0.32).move_to(thermA.get_bottom() + np.array([0, 0.46, 0])),
                      mercB.animate.stretch_to_fit_height(0.30).move_to(thermB.get_bottom() + np.array([0, 0.45, 0])),
                      mercC.animate.stretch_to_fit_height(0.30).move_to(thermC.get_bottom() + np.array([0, 0.45, 0])),
                      waterA.animate.set_fill(ManimColor("#3FA9F5")),
                      run_time=2.6, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 8.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="This is a great example of how energy moves and changes form. Different surfaces absorb different amounts of light, affecting how much the water warms up.") as tracker:
            sub = self.show_subtitle("This is a great example of how energy moves and changes form. Different surfaces absorb different amounts of light, affecting how much the water warms up.")
            self.play(FadeOut(scrim, shift=UP * 0.4), FadeOut(dark_group, shift=UP * 0.4), run_time=1.0, rate_func=rush_into)
            self.play(FadeIn(sun_star2, scale=0.5), FadeOut(decimals), FadeOut(cup_labels, shift=DOWN * 0.2), run_time=1.0, rate_func=smooth)
            self.play(AnimationGroup(*[FadeIn(p, shift=UP * 0.2) for p in chain], lag_ratio=0.25), run_time=2.2, rate_func=smooth)
            self.play(AnimationGroup(GrowArrow(mg), GrowArrow(N), GrowArrow(E_in_arrow), lag_ratio=0.25), run_time=1.7)
            self.play(FadeIn(mg_label), FadeIn(N_label), run_time=0.6)
            self.play(heroGroup.animate.shift(RIGHT * 4.2), mg.animate.shift(RIGHT * 4.2),
                      N.animate.shift(RIGHT * 4.2), mg_label.animate.shift(RIGHT * 4.2),
                      N_label.animate.shift(RIGHT * 4.2),
                      E_in_arrow.animate.put_start_and_end_on(sun_pos + np.array([-0.2, -0.7, 0]), rimB),
                      cupB.animate.set_opacity(0.25), cupC.animate.set_opacity(0.25),
                      waterB.animate.set_opacity(0.20), waterC.animate.set_opacity(0.20),
                      thermB.animate.set_opacity(0.25), thermC.animate.set_opacity(0.25),
                      mercB.animate.set_opacity(0.25), mercC.animate.set_opacity(0.25),
                      run_time=2.4, rate_func=smooth)
            self.play(Circumscribe(chain[2], color=ManimColor("#FF6B3D"), buff=0.15), run_time=1.3)
            self.play(Indicate(chain[4], scale_factor=1.8, color=ManimColor("#FF3B30")), run_time=1.1)
            self.wait(max(0.1, tracker.duration - 11.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So next time you see a cup in the sun, remember: it's not just holding your drink, it's also playing with light and energy!") as tracker:
            sub = self.show_subtitle("So next time you see a cup in the sun, remember: it's not just holding your drink, it's also playing with light and energy!")
            self.play(FadeOut(mg), FadeOut(N), FadeOut(mg_label), FadeOut(N_label),
                      FadeOut(E_in_arrow), FadeOut(chain, shift=UP * 0.3),
                      FadeOut(sun_star2), run_time=0.9, rate_func=rush_into)
            self.play(heroGroup.animate.shift(LEFT * 4.2),
                      cupB.animate.set_opacity(1.0), cupC.animate.set_opacity(1.0),
                      waterB.animate.set_opacity(0.55), waterC.animate.set_opacity(0.55),
                      thermB.animate.set_opacity(1.0), thermC.animate.set_opacity(1.0),
                      mercB.animate.set_opacity(1.0), mercC.animate.set_opacity(1.0),
                      run_time=2.0, rate_func=smooth)
            self.play(AnimationGroup(*[GrowArrow(r) for r in rays], lag_ratio=0.10), rays.animate.set_opacity(1.0), run_time=1.6)
            self.play(FadeIn(final_text, shift=DOWN * 0.3), FadeIn(key_group, shift=UP * 0.3), run_time=1.4, rate_func=smooth)
            self.play(FadeIn(result_group, shift=UP * 0.2), run_time=1.0, rate_func=smooth)
            self.play(Indicate(result_box, color=GOLD, scale_factor=1.06), run_time=0.9)
            self.wait(max(0.1, tracker.duration - 8.2))
            self.play(FadeOut(sub), run_time=0.4)