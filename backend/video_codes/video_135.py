from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.azure import AzureService
import numpy as np

import base64 as _b64_svg, os as _os

_SVG_DATA = {
    "thermometer": "PHN2ZyB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8Y2lyY2xlIGN4PSI1MCIgY3k9IjgwIiByPSIxMCIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyLjUiLz4KICA8cGF0aCBkPSJNIDQ0IDcwIEwgNDQgMjAgUSA0NCAxNSA1MCAxNSBRIDU2IDE1IDU2IDIwIEwgNTYgNzAiIHN0cm9rZT0id2hpdGUiIGZpbGw9Im5vbmUiIHN0cm9rZS13aWR0aD0iMi41Ii8+CiAgPGxpbmUgeDE9IjQ0IiB5MT0iNzAiIHgyPSI1NiIgeTI9IjcwIiBzdHJva2U9IndoaXRlIiBmaWxsPSJub25lIiBzdHJva2Utd2lkdGg9IjIuNSIvPgogIDxsaW5lIHgxPSI0NiIgeTE9IjQ1IiB4Mj0iNTQiIHkyPSI0NSIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyLjUiLz4KICA8bGluZSB4MT0iNDYiIHkxPSIzNSIgeDI9IjUyIiB5Mj0iMzUiIHN0cm9rZT0id2hpdGUiIGZpbGw9Im5vbmUiIHN0cm9rZS13aWR0aD0iMiIvPgogIDxsaW5lIHgxPSI0NiIgeTE9IjU1IiB4Mj0iNTIiIHkyPSI1NSIgc3Ryb2tlPSJ3aGl0ZSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyIi8+Cjwvc3ZnPg==",
    "light_bulb": "PHN2ZyB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiBzdHJva2U9IndoaXRlIiBmaWxsPSJub25lIiBzdHJva2Utd2lkdGg9IjIuNSI+CiAgPCEtLSBHbGFzcyBnbG9iZSAtLT4KICA8Y2lyY2xlIGN4PSI1MCIgY3k9IjQ1IiByPSIyOCIvPgogIDwhLS0gQ29udGFjdCBsaW5lcyBhdCBib3R0b20gLS0+CiAgPGxpbmUgeDE9IjQzIiB5MT0iNzMiIHgyPSI0MyIgeTI9IjgzIi8+CiAgPGxpbmUgeDE9IjU3IiB5MT0iNzMiIHgyPSI1NyIgeTI9IjgzIi8+CiAgPCEtLSBCYXNlIGNvbm5lY3RvciAtLT4KICA8bGluZSB4MT0iNDMiIHkxPSI4MyIgeDI9IjU3IiB5Mj0iODMiLz4KICA8bGluZSB4MT0iNDMiIHkxPSI3MyIgeDI9IjU3IiB5Mj0iNzMiLz4KICA8IS0tIEZpbGFtZW50IGNvaWwgaW5zaWRlIC0tPgogIDxwYXRoIGQ9Ik0gMzggNTAgUSA0MSA0NCA0NCA1MCBRIDQ3IDU2IDUwIDUwIFEgNTMgNDQgNTYgNTAgUSA1OSA1NiA2MiA1MCIgc3Ryb2tlLXdpZHRoPSIyIi8+CiAgPCEtLSBGaWxhbWVudCBsZWdzIC0tPgogIDxsaW5lIHgxPSIzOCIgeTE9IjUwIiB4Mj0iMzgiIHkyPSI2MCIvPgogIDxsaW5lIHgxPSI2MiIgeTE9IjUwIiB4Mj0iNjIiIHkyPSI2MCIvPgogIDxsaW5lIHgxPSIzOCIgeTE9IjYwIiB4Mj0iNjIiIHkyPSI2MCIvPgo8L3N2Zz4="
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


class ClosedCupEnergy(VoiceoverScene):
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

        title = Text("A closed cup.", font_size=28, color=WHITE).move_to(np.array([0, 2.9, 0]))

        title2 = Text("Energy always leaves.", font_size=28, color=WHITE).move_to(np.array([0, 2.9, 0]))

        # ═══ SETUP BLOCK: define all objects used below ═══
        HEAT = RED
        COLD = BLUE
        BULB = YELLOW

        background = Rectangle(width=15, height=9, fill_color=ManimColor("#0D1117"),
                                fill_opacity=1, stroke_width=0).move_to(ORIGIN)
        bench = Rectangle(width=10, height=0.3, fill_color=ManimColor("#3B3B3B"),
                           fill_opacity=1, stroke_width=0).move_to(np.array([0, -3.5, 0]))

        cup_body = RoundedRectangle(width=1.8, height=1.6, corner_radius=0.1, color=WHITE,
                                     fill_color=GREY_D, fill_opacity=0.3).move_to(ORIGIN)
        lid = Rectangle(width=2.0, height=0.25, color=WHITE, fill_color=GREY_D,
                         fill_opacity=0.5).move_to(cup_body.get_top() + UP * 0.15)
        liquid = Rectangle(width=1.5, height=0.9, color=BLUE, fill_color=BLUE,
                            fill_opacity=0.6).move_to(cup_body.get_center() + DOWN * 0.2)
        cup = VGroup(cup_body, lid, liquid)

        steam = VGroup(*[
            Line(cup.get_top() + UP * 0.1 + RIGHT * x, cup.get_top() + UP * 0.5 + RIGHT * x,
                 color=WHITE, stroke_width=2)
            for x in [-0.3, 0, 0.3]
        ])

        heat_arrows = VGroup(
            Arrow(np.array([2.6, 2.0, 0]), cup_body.get_right() + UP * 0.3, color=HEAT, buff=0.1),
            Arrow(np.array([2.6, 0.5, 0]), cup_body.get_right(), color=HEAT, buff=0.1),
            Arrow(np.array([2.6, -1.0, 0]), cup_body.get_right() + DOWN * 0.3, color=HEAT, buff=0.1),
        )
        label_Q = MathTex("Q_{in}", color=HEAT).next_to(heat_arrows, UP)

        cold_arrows = VGroup(
            Arrow(cup_body.get_left(), np.array([-2.6, 0.5, 0]), color=COLD, buff=0.1),
            Arrow(cup_body.get_left() + DOWN * 0.3, np.array([-2.6, -1.0, 0]), color=COLD, buff=0.1),
        )
        label_cold = MathTex("Q_{out}", color=COLD).next_to(cold_arrows, DOWN)

        cross_x = Cross(scale_factor=0.5, stroke_color=RED).move_to(cold_arrows.get_center())

        wall_in = Line(cup_body.get_corner(UL) + LEFT * 0.3, cup_body.get_corner(DL) + LEFT * 0.3,
                        color=GREY_B, stroke_width=4)
        wall_out = Line(cup_body.get_corner(UR) + RIGHT * 0.3, cup_body.get_corner(DR) + RIGHT * 0.3,
                         color=GREY_B, stroke_width=4)
        vacuum = Rectangle(width=0.5, height=1.8, color=GREY_B, fill_opacity=0.1).move_to(
            cup_body.get_right() + RIGHT * 0.5)
        vacuum_txt = Text("vacuum", font_size=16, color=GREY_B).move_to(vacuum.get_center())
        wall_cut = Rectangle(width=2.6, height=2.0, color=GREY_B, stroke_width=2).move_to(cup_body.get_center())

        cond = Arrow(cup_body.get_bottom() + DOWN * 0.1, cup_body.get_bottom() + DOWN * 0.8, color=ORANGE, buff=0.05)
        conv = Arrow(cup_body.get_left() + LEFT * 0.1, cup_body.get_left() + LEFT * 0.8, color=YELLOW, buff=0.05)
        rad = Arrow(cup_body.get_top() + UP * 0.1, cup_body.get_top() + UP * 0.8, color=RED, buff=0.05)
        transfer_lbls = VGroup(
            Text("Conduction", font_size=14).next_to(cond, DOWN),
            Text("Convection", font_size=14).next_to(conv, LEFT),
            Text("Radiation", font_size=14).next_to(rad, UP),
        )

        light_bulb_svg = get_svg("light_bulb", height=0.9).move_to(np.array([0, -2.5, 0]))

        eq = MathTex(r"\Delta U = Q_{in} - Q_{out}", color=WHITE).move_to(np.array([0, -3.2, 0]))

        moving_group = VGroup(cup, heat_arrows, wall_in, wall_out, vacuum, vacuum_txt, cond, conv, rad, wall_cut)

        cup_open = RoundedRectangle(width=1.8, height=1.4, corner_radius=0.1, color=WHITE,
                                     fill_color=GREY_D, fill_opacity=0.3).move_to(np.array([3.5, 0, 0]))
        steam_open = VGroup(*[
            Line(cup_open.get_top() + UP * 0.1 + RIGHT * x, cup_open.get_top() + UP * 0.6 + RIGHT * x,
                 color=WHITE, stroke_width=2)
            for x in [-0.3, 0, 0.3]
        ])

        thermo_L = get_svg("thermometer", height=1.1).move_to(np.array([-3.2, -1.6, 0]))
        thermo_R = get_svg("thermometer", height=1.1).move_to(np.array([3.5, -1.6, 0]))

        merc_L = Rectangle(width=0.15, height=0.6, fill_color=RED, fill_opacity=1,
                            stroke_width=0).move_to(thermo_L.get_center() + DOWN * 0.1)
        merc_R = Rectangle(width=0.15, height=0.6, fill_color=RED, fill_opacity=1,
                            stroke_width=0).move_to(thermo_R.get_center() + DOWN * 0.1)

        W = Arrow(cup_open.get_top(), cup_open.get_top() + UP * 0.8, color=COLD, buff=0.05)
        N = Arrow(cup_open.get_right(), cup_open.get_right() + RIGHT * 0.8, color=HEAT, buff=0.05)

        cap_L = Triangle(color=YELLOW, fill_opacity=0.6).scale(0.3).move_to(np.array([-3.2, 1.6, 0]))
        cap_R = Rectangle(width=0.4, height=0.6, color=BLUE, fill_opacity=0.4).move_to(np.array([3.5, 1.6, 0]))
        captions = VGroup(
            Text("Lamp", font_size=14).next_to(cap_L, DOWN, buff=0.1),
            Text("Fridge", font_size=14).next_to(cap_R, DOWN, buff=0.1),
        )
        room_lbl = Text("Room", font_size=16).move_to(np.array([0, 3.3, 0]))

        temp_L = Text("Closed:", font_size=16).move_to(np.array([-3.2, -2.3, 0]))
        temp_R = Text("Open:", font_size=16).move_to(np.array([3.5, -2.3, 0]))
        t_closed = DecimalNumber(20.0, num_decimal_places=1, color=WHITE).next_to(temp_L, RIGHT, buff=0.1)
        t_open = DecimalNumber(20.0, num_decimal_places=1, color=WHITE).next_to(temp_R, RIGHT, buff=0.1)

        clock = VGroup(
            Circle(radius=0.3, color=WHITE),
            Line(ORIGIN, UP * 0.2),
            Line(ORIGIN, RIGHT * 0.15),
        ).move_to(np.array([5.8, 2.5, 0]))

        delta_text = MathTex(r"\Delta T_{closed} > \Delta T_{open}", color=WHITE).move_to(np.array([0, -3.5, 0]))

        bulb_glow = Circle(radius=0.6, color=BULB, fill_opacity=0.3, stroke_width=0).move_to(
            light_bulb_svg.get_center())
        A_final = Arrow(light_bulb_svg.get_center(), light_bulb_svg.get_center() + RIGHT * 1.5,
                         color=BULB, buff=0.1)

        closing = Text("Energy moves. Matter stays.", font_size=26, color=WHITE).move_to(np.array([0, -1.0, 0]))

        self.add(background, bench)
        # ═══ PHASE 2: ANIMATIONS START HERE ═══
        with self.voiceover(text="Imagine a cup with a lid. Inside, there's a liquid. But here's the twist: nothing can get in or out. So, how does the liquid's temperature change?") as tracker:
            sub = self.show_subtitle("Imagine a cup with a lid. Inside, there's a liquid. But nothing can get in or out. So how does its temperature change?")
            self.play(DrawBorderThenFill(cup_body), run_time=1.6, rate_func=smooth)
            self.play(FadeIn(lid, shift=DOWN * 0.6), run_time=0.8, rate_func=rush_from)
            self.play(FadeIn(liquid, shift=UP * 0.3), run_time=0.7, rate_func=smooth)
            self.play(FadeIn(title, shift=DOWN * 0.4), run_time=0.9, rate_func=smooth)
            self.play(steam.animate.set_opacity(0.4), run_time=1.0, rate_func=there_and_back)
            self.wait(max(0.1, tracker.duration - 5.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Think about sunlight warming your skin. Light or heat can enter the cup and warm the liquid.") as tracker:
            sub = self.show_subtitle("Think about sunlight warming your skin. Light or heat can enter the cup and warm the liquid.")
            self.play(AnimationGroup(*[GrowArrow(a) for a in heat_arrows], lag_ratio=0.25), run_time=2.4)
            self.play(FadeIn(label_Q, shift=RIGHT * 0.2), run_time=0.8, rate_func=smooth)
            self.play(heat_arrows.animate.set_stroke(opacity=0.55), run_time=0.9, rate_func=there_and_back)
            self.play(Transform(title, title2), run_time=1.0, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 5.3))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="If it's cold outside, the liquid might cool down.") as tracker:
            sub = self.show_subtitle("If it's cold outside, the liquid might cool down.")
            self.play(AnimationGroup(*[GrowArrow(c) for c in cold_arrows], lag_ratio=0.25), run_time=2.2)
            self.play(FadeIn(label_cold, shift=UP * 0.2), run_time=0.8, rate_func=smooth)
            self.play(Indicate(label_cold, scale_factor=1.15, color=COLD), run_time=0.8)
            self.wait(max(0.1, tracker.duration - 4.2))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="We can draw or imagine how energy moves into or out of the cup. This helps us understand how the liquid's temperature changes.") as tracker:
            sub = self.show_subtitle("We can imagine how energy moves into or out of the cup. That explains how the liquid's temperature changes.")
            self.play(Create(cross_x), run_time=0.5, rate_func=smooth)
            self.play(FadeOut(cold_arrows, shift=RIGHT * 0.2), FadeOut(cross_x), FadeOut(label_cold, shift=DOWN * 0.2), run_time=0.8, rate_func=rush_into)
            self.play(AnimationGroup(FadeIn(wall_in, shift=RIGHT * 0.3), FadeIn(vacuum), FadeIn(vacuum_txt), FadeIn(wall_out, shift=RIGHT * 0.3), FadeIn(wall_cut), lag_ratio=0.25), run_time=1.5)
            self.play(AnimationGroup(GrowArrow(cond), GrowArrow(conv), GrowArrow(rad), lag_ratio=0.25), run_time=1.6)
            self.play(AnimationGroup(*[FadeIn(l, shift=UP * 0.15) for l in transfer_lbls], lag_ratio=0.25), run_time=1.0)
            self.play(FadeIn(light_bulb_svg, shift=DOWN * 0.4), run_time=0.7, rate_func=smooth)
            self.play(Flash(light_bulb_svg, color=BULB, num_lines=12, flash_radius=0.7), run_time=0.6)
            self.play(FadeIn(eq, shift=UP * 0.2), cond.animate.set_stroke(opacity=0.15), conv.animate.set_stroke(opacity=0.15), run_time=1.2, rate_func=smooth)
            self.play(Indicate(eq, scale_factor=1.1, color=BULB), run_time=0.8)
            self.wait(max(0.1, tracker.duration - 9.3))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="We can try putting the cup in different places, like under a lamp or in a fridge, to see how the liquid's temperature changes.") as tracker:
            sub = self.show_subtitle("We can put the cup in different places, like under a lamp or in a fridge, and watch the temperature.")
            self.play(moving_group.animate.shift(LEFT * 3.2), FadeOut(eq, shift=LEFT * 0.3), FadeOut(label_Q, shift=RIGHT * 0.3), FadeOut(transfer_lbls, shift=DOWN * 0.3), FadeOut(title), run_time=1.6, rate_func=smooth)
            self.play(FadeIn(cup_open, shift=LEFT * 0.5), FadeIn(steam_open, shift=UP * 0.2), run_time=0.9, rate_func=smooth)
            self.play(AnimationGroup(FadeIn(thermo_L, shift=DOWN * 0.5), FadeIn(thermo_R, shift=DOWN * 0.5), lag_ratio=0.25), run_time=1.2)
            self.play(FadeIn(merc_L), FadeIn(merc_R), run_time=0.5, rate_func=smooth)
            self.play(AnimationGroup(GrowArrow(W), GrowArrow(N), lag_ratio=0.25), run_time=0.9)
            self.play(W.animate.set_opacity(0.25), N.animate.set_opacity(0.25), run_time=0.6, rate_func=smooth)
            self.play(AnimationGroup(FadeIn(cap_L, shift=UP * 0.2), FadeIn(cap_R, shift=UP * 0.2), FadeIn(captions), lag_ratio=0.25), light_bulb_svg.animate.move_to(np.array([0, 2.4, 0])).scale(0.9), FadeIn(room_lbl), run_time=1.1, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 6.9))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So, the temperature of the liquid in a closed cup changes because of energy interactions, not because anything enters or leaves the cup.") as tracker:
            sub = self.show_subtitle("The liquid's temperature changes because of energy interactions — not because matter enters or leaves.")
            self.play(FadeIn(temp_L, shift=DOWN * 0.2), FadeIn(temp_R, shift=DOWN * 0.2), FadeIn(t_closed), FadeIn(t_open), run_time=0.7, rate_func=smooth)
            self.play(
                t_closed.animate.set_value(88.4),
                t_open.animate.set_value(63.7),
                merc_L.animate.stretch_to_fit_height(0.93).move_to(np.array([-3.2, 0.415, 0])),
                merc_R.animate.stretch_to_fit_height(0.35).move_to(np.array([3.2, 0.125, 0])),
                FadeIn(clock),
                steam_open.animate.set_opacity(0.0),
                run_time=3.0, rate_func=smooth,
            )
            self.play(cup_open.animate.set_color(ManimColor("#78909C")), temp_R.animate.set_color(COLD), run_time=0.8, rate_func=smooth)
            self.play(Circumscribe(cup, color=HEAT, buff=0.25, stroke_width=6), run_time=1.2)
            self.play(temp_L.animate.scale(1.35).set_color(BULB), run_time=0.4, rate_func=smooth)
            self.play(temp_L.animate.scale(1 / 1.35), run_time=0.3, rate_func=smooth)
            self.play(FadeIn(delta_text, shift=UP * 0.2), run_time=1.0, rate_func=smooth)
            self.play(Indicate(delta_text, scale_factor=1.1, color=HEAT), run_time=0.8)
            self.wait(max(0.1, tracker.duration - 8.8))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Next time you sip a warm drink, remember, it's all about energy moving around!") as tracker:
            sub = self.show_subtitle("Next time you sip a warm drink, remember — it's all about energy moving around!")
            self.play(FadeOut(cup_open, shift=DOWN * 0.4), FadeOut(steam_open), FadeOut(thermo_R, shift=DOWN * 0.4), FadeOut(temp_R), FadeOut(captions, shift=DOWN * 0.4), FadeOut(clock), FadeOut(delta_text), FadeOut(W), FadeOut(N), FadeOut(wall_cut), FadeOut(vacuum), FadeOut(vacuum_txt), FadeOut(cond), FadeOut(conv), FadeOut(rad), FadeOut(thermo_L), FadeOut(temp_L), FadeOut(merc_L), FadeOut(merc_R), FadeOut(room_lbl), FadeOut(steam), run_time=1.1, rate_func=rush_into)
            self.play(VGroup(cup, heat_arrows).animate.move_to(np.array([0, 0.2, 0])), run_time=1.3, rate_func=smooth)
            self.play(FadeOut(heat_arrows, shift=UP * 0.2), run_time=0.7, rate_func=rush_into)
            self.play(FadeIn(bulb_glow), GrowArrow(A_final), run_time=0.7, rate_func=smooth)
            self.play(Indicate(light_bulb_svg, scale_factor=1.15, color=BULB), run_time=0.8)
            self.play(FadeIn(closing, shift=UP * 0.3), run_time=1.3, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 6.4))
            self.play(FadeOut(sub), run_time=0.4)

        self.play(FadeOut(Group(*self.mobjects), shift=DOWN * 0.3), run_time=1.2, rate_func=rush_into)