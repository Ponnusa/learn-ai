from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.azure import AzureService
import numpy as np

import base64 as _b64_svg, os as _os

_SVG_DATA = {
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


class ColdCupSweat(VoiceoverScene):
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

        # ═══ SETUP BLOCK: define all objects before first voiceover ═══
        LIQ = ManimColor("#3AA9FF")
        ACCENT = ManimColor("#FFD166")

        background = Rectangle(width=15, height=9, stroke_width=0,
                                fill_color=ManimColor("#0E1117"), fill_opacity=1).move_to(ORIGIN)

        cup_left_pos = LEFT * 4.2
        cup_final_pos = RIGHT * 1.4  # cup_left_pos + RIGHT*5.6

        cup_body = RoundedRectangle(width=1.6, height=2.4, corner_radius=0.15, color=WHITE).move_to(ORIGIN)
        cup_liquid = Rectangle(width=1.3, height=1.0, color=LIQ, fill_opacity=0.6).move_to(
            cup_body.get_center() + DOWN * 0.4)
        ice = VGroup(*[
            Circle(radius=0.12, color=WHITE, fill_opacity=0.9).move_to(cup_liquid.get_center() + np.array([x, y, 0]))
            for x, y in [(-0.3, 0.2), (0.25, 0.15), (0, -0.15)]
        ])
        cup_label = Text("Cold Drink", font_size=20).next_to(cup_body, UP, buff=0.2)
        temp = Text("4°C", font_size=20, color=LIQ).next_to(cup_body, RIGHT, buff=0.3)

        cup = VGroup(cup_body, cup_liquid, ice)

        q_mark = Text("?", font_size=72, color=ACCENT).move_to(UP * 2.5)
        q_text = Text("Where do they come from?", font_size=24).next_to(q_mark, DOWN, buff=0.3)

        air_box = Rectangle(width=3.5, height=3.5, color=GREY_B).move_to(RIGHT * 3.2)
        air_label = Text("Air", font_size=22).next_to(air_box, UP, buff=0.2)
        air_temp = Text("25°C", font_size=20, color=RED).next_to(air_box, DOWN, buff=0.2)

        np.random.seed(42)
        vapor = VGroup(*[
            Dot(radius=0.05, color=BLUE_B).move_to(
                air_box.get_center() + np.array([np.random.uniform(-1.5, 1.5), np.random.uniform(-1.5, 1.5), 0]))
            for _ in range(24)
        ])

        h2o_gas = MathTex("H_2O_{(g)}", font_size=28).next_to(air_box, UP, buff=0.6)
        humidity = Text("Humidity: 60%", font_size=20).next_to(h2o_gas, DOWN, buff=0.15)

        near_vapor = VGroup(*vapor[:8])

        cold_halo = Circle(radius=1.4, color=BLUE_A, stroke_opacity=0.5).move_to(cup_left_pos)
        grav_arrow = Arrow(start=cup_left_pos + UP * 0.2, end=cup_left_pos + DOWN * 1.0, color=WHITE, buff=0)

        cup_move_path = Line(cup_left_pos, cup_final_pos)

        drops = VGroup(*[
            Dot(radius=0.06, color=LIQ).move_to(
                cup_final_pos + np.array([np.random.uniform(-0.6, 0.6), np.random.uniform(-1.0, 1.0), 0]))
            for _ in range(10)
        ])
        cond_text = Text("Condensation!", font_size=24, color=LIQ).move_to(cup_final_pos + UP * 1.8)

        eq_gas = MathTex("H_2O_{(g)}", font_size=32).move_to(UP * 2.6 + LEFT * 2.0)
        eq_arrow = Arrow(UP * 2.6 + LEFT * 0.8, UP * 2.6 + RIGHT * 0.8, color=WHITE, buff=0.1)
        eq_liq = MathTex("H_2O_{(l)}", font_size=32).move_to(UP * 2.6 + RIGHT * 2.0)

        transform_pairs = list(near_vapor[:6])
        transform_targets = [d.copy().set_color(LIQ) for d in drops[:6]]

        zoom_ring = Circle(radius=1.0, color=ACCENT).move_to(cup_final_pos + DOWN * 0.2)
        big_drops = VGroup(*[
            Dot(radius=0.15, color=LIQ).move_to(zoom_ring.get_center() + np.array([dx, dy, 0]))
            for dx, dy in [(-0.3, 0.2), (0.3, 0.1), (0, -0.3)]
        ])
        pure_text = Text("Pure Water", font_size=22, color=LIQ).next_to(zoom_ring, DOWN, buff=0.3)

        drop_count = DecimalNumber(0, num_decimal_places=0, font_size=28).next_to(zoom_ring, UP, buff=0.3)
        drop_count_label = Text("droplets", font_size=18).next_to(drop_count, RIGHT, buff=0.15)

        heat_arrows = VGroup(*[
            Arrow(air_box.get_center() + np.array([0, dy, 0]), cup_final_pos + np.array([0, dy, 0]),
                  color=RED, buff=0.1)
            for dy in [0.6, 0.0, -0.6]
        ])
        latent_label = Text("Latent Heat Release", font_size=22, color=ACCENT).next_to(heat_arrows, UP, buff=0.3)

        cold_arrows = VGroup(*[
            Arrow(cup_final_pos + np.array([dx, dy, 0]), cup_final_pos + np.array([dx * 1.8, dy * 1.8, 0]),
                  color=BLUE, buff=0.05)
            for dx, dy in [(0.5, 0.5), (-0.5, 0.5), (0, 0.7)]
        ])

        all_arrows = VGroup(heat_arrows, cold_arrows)

        cup_and_drops = VGroup(cup, drops)

        scale_svg = get_svg("balance_scale", height=1.5).move_to(LEFT * 5.2 + UP * 2.4)
        left_pan_label = Text("Air", font_size=18).next_to(scale_svg, LEFT, buff=0.3)
        right_pan_label = Text("Cup", font_size=18).next_to(scale_svg, RIGHT, buff=0.3)
        rate_eq = MathTex(r"\text{Rate}_{evap} = \text{Rate}_{cond}", font_size=28).next_to(scale_svg, DOWN, buff=0.4)

        final_line = Text("Water vapor becomes visible droplets!", font_size=26, color=ACCENT).move_to(DOWN * 2.5)

        self.add(background)
        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Have you ever noticed water droplets forming on the outside of a cold cup?") as tracker:
            sub = self.show_subtitle("Have you ever noticed water droplets forming on the outside of a cold cup?")
            self.play(FadeIn(cup_body, shift=UP * 0.8), run_time=1.4, rate_func=smooth)
            self.play(DrawBorderThenFill(cup_liquid), run_time=1.2, rate_func=smooth)
            self.play(AnimationGroup(*[FadeIn(c, shift=DOWN * 0.3) for c in ice], lag_ratio=0.3),
                      run_time=1.0, rate_func=smooth)
            self.play(FadeIn(cup_label, shift=UP * 0.2), FadeIn(temp, shift=RIGHT * 0.4),
                      run_time=1.0, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 4.8))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="But where do these droplets come from?") as tracker:
            sub = self.show_subtitle("But where do these droplets come from?")
            self.play(Create(q_mark), run_time=1.6, rate_func=smooth)
            self.play(FadeIn(q_text, shift=UP * 0.4), run_time=1.0, rate_func=smooth)
            self.play(q_mark.animate.shift(UP * 0.15), run_time=1.2, rate_func=there_and_back)
            self.wait(max(0.1, tracker.duration - 3.9))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Let's explore this mystery!") as tracker:
            sub = self.show_subtitle("Let's explore this mystery!")
            self.play(FadeOut(q_text, shift=DOWN * 0.3), FadeOut(temp, shift=RIGHT * 0.3),
                      FadeOut(cup_label, shift=DOWN * 0.3),
                      q_mark.animate.scale(0.4).move_to(RIGHT * 6.0 + UP * 3.1),
                      run_time=1.2, rate_func=rush_into)
            self.play(AnimationGroup(cup.animate.shift(LEFT * 4.2),
                                     DrawBorderThenFill(air_box),
                                     FadeIn(air_label, shift=DOWN * 0.2),
                                     FadeIn(air_temp, shift=DOWN * 0.3),
                                     lag_ratio=0.25),
                      run_time=3.0, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 4.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Imagine the air around us is like a big invisible ocean. It's full of tiny water droplets, even if we can't see them.") as tracker:
            sub = self.show_subtitle("Imagine the air around us is like a big invisible ocean. It's full of tiny water droplets, even if we can't see them.")
            self.play(AnimationGroup(*[FadeIn(d, scale=0.4) for d in vapor], lag_ratio=0.06),
                      run_time=2.6, rate_func=smooth)
            self.play(FadeIn(h2o_gas, shift=UP * 0.3), FadeIn(humidity, shift=UP * 0.3),
                      run_time=1.2, rate_func=smooth)
            self.play(AnimationGroup(*[d.animate.shift(UP * 0.12) for d in vapor], lag_ratio=0.02),
                      run_time=1.4, rate_func=there_and_back)
            self.wait(max(0.1, tracker.duration - 5.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="When a cold cup enters this ocean, something magical happens.") as tracker:
            sub = self.show_subtitle("When a cold cup enters this ocean, something magical happens.")
            self.play(FadeIn(cold_halo), GrowArrow(grav_arrow), run_time=1.0, rate_func=smooth)
            self.play(AnimationGroup(MoveAlongPath(cup, cup_move_path),
                                     cold_halo.animate.shift(RIGHT * 5.6),
                                     grav_arrow.animate.shift(RIGHT * 5.6),
                                     lag_ratio=0.0),
                      run_time=2.6, rate_func=smooth)
            self.play(AnimationGroup(*[d.animate.set_color(ManimColor("#BFD9F2")) for d in near_vapor],
                                     lag_ratio=0.15), run_time=1.4, rate_func=smooth)
            self.play(FadeOut(grav_arrow, shift=DOWN * 0.3), run_time=0.6, rate_func=rush_into)
            self.wait(max(0.1, tracker.duration - 5.8))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="The cold surface of the cup cools down the air around it.") as tracker:
            sub = self.show_subtitle("The cold surface of the cup cools down the air around it.")
            self.play(Flash(cup, color=LIQ, line_length=0.5, num_lines=18, flash_radius=1.9),
                      run_time=0.9, rate_func=smooth)
            self.play(AnimationGroup(*[GrowFromCenter(d) for d in drops], lag_ratio=0.05),
                      run_time=1.2, rate_func=smooth)
            self.play(Indicate(cup_body, scale_factor=1.12, color=LIQ), run_time=0.8)
            self.play(cup_body.animate.set_stroke(LIQ, width=7), FadeIn(cond_text, shift=UP * 0.3),
                      run_time=1.0, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 4.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="This cooling causes the water vapor in the air to turn into liquid droplets on the cup's surface.") as tracker:
            sub = self.show_subtitle("This cooling causes the water vapor in the air to turn into liquid droplets on the cup's surface.")
            self.play(FadeOut(cond_text, shift=DOWN * 0.3), run_time=0.5, rate_func=rush_into)
            self.play(AnimationGroup(FadeIn(eq_gas, shift=UP * 0.2), GrowArrow(eq_arrow),
                                     FadeIn(eq_liq, shift=UP * 0.2), lag_ratio=0.25),
                      run_time=2.2, rate_func=smooth)
            self.play(Indicate(eq_liq, color=LIQ), run_time=0.8)
            self.play(AnimationGroup(*[Transform(transform_pairs[i], transform_targets[i])
                                       for i in range(len(transform_pairs))], lag_ratio=0.2),
                      run_time=2.8, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 6.7))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="And that's why the droplets are clear—they come from the air, not the drink inside!") as tracker:
            sub = self.show_subtitle("And that's why the droplets are clear - they come from the air, not the drink inside!")
            self.play(Circumscribe(drops, shape=Circle, color=ACCENT, buff=0.25), run_time=1.3)
            self.play(FadeOut(vapor, shift=RIGHT * 0.3), FadeOut(h2o_gas, shift=DOWN * 0.2),
                      FadeOut(humidity, shift=DOWN * 0.2), run_time=0.8, rate_func=rush_into)
            self.play(Create(zoom_ring),
                      AnimationGroup(*[GrowFromCenter(b) for b in big_drops], lag_ratio=0.2),
                      FadeIn(pure_text, shift=UP * 0.2), run_time=1.4, rate_func=smooth)
            self.play(FadeIn(drop_count), FadeIn(drop_count_label), run_time=0.6, rate_func=smooth)
            self.play(drop_count.animate.set_value(14), drops.animate.set_color(ManimColor("#5FC4FF")),
                      run_time=1.4, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 5.9))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="This is a perfect example of energy moving from warmer to cooler areas.") as tracker:
            sub = self.show_subtitle("This is a perfect example of energy moving from warmer to cooler areas.")
            self.play(FadeOut(zoom_ring, shift=RIGHT * 0.3), FadeOut(big_drops, shift=RIGHT * 0.3),
                      FadeOut(pure_text, shift=DOWN * 0.2), FadeOut(drop_count, shift=DOWN * 0.2),
                      FadeOut(drop_count_label, shift=DOWN * 0.2), run_time=0.9, rate_func=rush_into)
            self.play(AnimationGroup(*[GrowArrow(a) for a in heat_arrows], lag_ratio=0.25),
                      run_time=2.0, rate_func=smooth)
            self.play(FadeIn(latent_label, shift=UP * 0.2), run_time=1.0, rate_func=smooth)
            self.play(AnimationGroup(*[GrowArrow(a) for a in cold_arrows], lag_ratio=0.25),
                      run_time=1.4, rate_func=smooth)
            self.play(cup.animate.shift(UP * 0.12), drops.animate.shift(UP * 0.12),
                      all_arrows.animate.shift(UP * 0.12), run_time=0.8, rate_func=there_and_back)
            self.wait(max(0.1, tracker.duration - 6.1))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Eventually, everything reaches a balance, or equilibrium.") as tracker:
            sub = self.show_subtitle("Eventually, everything reaches a balance, or equilibrium.")
            self.play(FadeOut(all_arrows, shift=RIGHT * 0.3), FadeOut(latent_label, shift=UP * 0.2),
                      FadeOut(eq_gas, shift=LEFT * 0.3), FadeOut(eq_arrow, shift=LEFT * 0.3),
                      FadeOut(eq_liq, shift=LEFT * 0.3), FadeOut(air_box, shift=RIGHT * 0.4),
                      FadeOut(air_label, shift=UP * 0.2), FadeOut(air_temp, shift=RIGHT * 0.3),
                      FadeOut(cold_halo), run_time=1.1, rate_func=rush_into)
            self.play(cup_and_drops.animate.scale(0.55).move_to(LEFT * 4.3 + UP * 2.0),
                      run_time=1.0, rate_func=smooth)
            self.play(FadeIn(scale_svg, shift=UP * 0.5), run_time=1.4, rate_func=smooth)
            self.play(AnimationGroup(FadeIn(left_pan_label, shift=UP * 0.2),
                                     FadeIn(right_pan_label, shift=UP * 0.2), lag_ratio=0.25),
                      run_time=1.2, rate_func=smooth)
            self.play(Rotate(scale_svg, angle=-6 * DEGREES,
                             about_point=scale_svg.get_center() + UP * 0.6),
                      FadeIn(rate_eq, shift=UP * 0.2), run_time=1.2, rate_func=smooth)
            self.play(Indicate(rate_eq, color=ACCENT), run_time=0.8)
            self.wait(max(0.1, tracker.duration - 7.1))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So next time you see droplets on your cold drink, remember—they're a little gift from the air around you, not a leak from your cup!") as tracker:
            sub = self.show_subtitle("So next time you see droplets on your cold drink, remember - they're a little gift from the air around you, not a leak from your cup!")
            self.play(FadeOut(scale_svg, shift=DOWN * 0.4), FadeOut(left_pan_label, shift=LEFT * 0.3),
                      FadeOut(right_pan_label, shift=RIGHT * 0.3), FadeOut(rate_eq, shift=DOWN * 0.3),
                      run_time=1.1, rate_func=rush_into)
            self.play(cup_and_drops.animate.scale(1.9).move_to(ORIGIN), run_time=1.4, rate_func=smooth)
            self.play(q_mark.animate.scale(2.2).move_to(RIGHT * 2.8 + UP * 1.5).set_color(LIQ),
                      run_time=1.0, rate_func=smooth)
            self.play(FadeOut(q_mark, scale=0.3), run_time=0.8, rate_func=rush_into)
            self.play(FadeIn(final_line, shift=UP * 0.3), run_time=1.2, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 6.0))
            self.play(FadeOut(sub), run_time=0.4)

        self.play(FadeOut(cup_and_drops, shift=DOWN * 0.4), FadeOut(final_line, shift=DOWN * 0.3),
                  run_time=1.4, rate_func=rush_into)