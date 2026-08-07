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


class WhyLidKeepsDrinkHot(VoiceoverScene):
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

        # ═══ SETUP BLOCK: define every object used throughout the scene ═══
        COLD = ManimColor("#4FC3F7")
        HOT = ManimColor("#FF7043")
        rng = np.random.default_rng(42)

        background = Rectangle(width=15, height=9, fill_color=self.camera.background_color,
                                fill_opacity=1, stroke_width=0)

        # Title
        line1 = Text("How does the design of a cup", font_size=30, color=WHITE).move_to(UP * 2.6)
        line2 = Text("affect how long your drink stays warm?", font_size=30, color=WHITE).move_to(UP * 2.0)

        # Main thermometer + temperature readout
        thermo_main = get_svg("thermometer", height=0.8)
        thermo_main.scale(2.2 / max(thermo_main.height, 0.01))
        thermo_main.move_to(RIGHT * 4.5 + UP * 0.2)
        temp_tracker = ValueTracker(85.0)
        temp_display = always_redraw(
            lambda: Text(f"{temp_tracker.get_value():.1f} °C", font_size=28, color=HOT)
            .next_to(thermo_main, DOWN, buff=0.22)
        )

        # Sealed thermometer (used later)
        thermo_sealed = get_svg("thermometer", height=0.8)
        thermo_sealed.scale(2.6 / max(thermo_sealed.height, 0.01))
        thermo_sealed.move_to(LEFT * 5.4 + UP * 0.2)
        sealed_tracker = ValueTracker(85.0)
        sealed_display = always_redraw(
            lambda: Text(f"{sealed_tracker.get_value():.1f} °C", font_size=28, color=COLD)
            .next_to(thermo_sealed, DOWN, buff=0.22)
        )
        sealed_tag = Text("SEALED", font_size=28, color=COLD).next_to(thermo_sealed, UP, buff=0.2)
        no_escape_text = Text("No escape = no evaporative loss", font_size=28, color=COLD).move_to(DOWN * 2.15)

        # Two cups
        cupA_body = RoundedRectangle(width=1.6, height=2.0, corner_radius=0.1, color=WHITE, stroke_width=3) \
            .move_to(LEFT * 3 + DOWN * 0.6)
        cupB_body = RoundedRectangle(width=1.6, height=2.0, corner_radius=0.1, color=WHITE, stroke_width=3) \
            .move_to(RIGHT * 3 + DOWN * 0.6)
        cupA_liquid = Rectangle(width=1.3, height=1.0, fill_color=HOT, fill_opacity=0.75, stroke_width=0) \
            .move_to(cupA_body.get_bottom() + UP * 0.55)
        cupB_liquid = Rectangle(width=1.3, height=1.0, fill_color=HOT, fill_opacity=0.75, stroke_width=0) \
            .move_to(cupB_body.get_bottom() + UP * 0.55)
        lidA = Rectangle(width=1.7, height=0.15, fill_color=GRAY_B, fill_opacity=1, stroke_width=1) \
            .next_to(cupA_body, UP, buff=0.0)
        lidB = Rectangle(width=1.7, height=0.15, fill_color=GRAY_B, fill_opacity=1, stroke_width=1) \
            .next_to(cupB_body, UP, buff=0.0)
        labelA = Text("Tight Lid", font_size=24, color=COLD).next_to(cupA_body, DOWN, buff=0.35)
        labelB = Text("Loose Lid", font_size=24, color=HOT).next_to(cupB_body, DOWN, buff=0.35)
        cupA = VGroup(cupA_body, cupA_liquid, lidA)
        cupB = VGroup(cupB_body, cupB_liquid, lidB)

        # Particle dots inside liquids
        dotsA = VGroup(*[
            Dot(radius=0.05, color=WHITE).move_to(
                cupA_liquid.get_center() + np.array([rng.uniform(-0.5, 0.5), rng.uniform(-0.35, 0.35), 0])
            ) for _ in range(12)
        ])
        dotsB = VGroup(*[
            Dot(radius=0.05, color=WHITE).move_to(
                cupB_liquid.get_center() + np.array([rng.uniform(-0.5, 0.5), rng.uniform(-0.35, 0.35), 0])
            ) for _ in range(12)
        ])

        caption_heat = Text("Heat = particles in motion", font_size=26, color=HOT).move_to(DOWN * 2.6)

        # Heat-flow arrows leaving each cup
        arrowsA = VGroup(*[
            Arrow(cupA_liquid.get_top() + RIGHT * dx, cupA_liquid.get_top() + RIGHT * dx + UP * 0.9,
                  buff=0, color=HOT, stroke_width=4, max_tip_length_to_length_ratio=0.25)
            for dx in [-0.35, 0, 0.35]
        ])
        arrowsB = VGroup(*[
            Arrow(cupB_liquid.get_top() + RIGHT * dx, cupB_liquid.get_top() + RIGHT * dx + UP * 0.9,
                  buff=0, color=HOT, stroke_width=4, max_tip_length_to_length_ratio=0.25)
            for dx in [-0.35, 0, 0.35]
        ])
        arrowsA_side = VGroup(*[
            Arrow(cupA_body.get_right() + UP * dy, cupA_body.get_right() + RIGHT * 0.7 + UP * dy,
                  buff=0, color=HOT, stroke_width=3, max_tip_length_to_length_ratio=0.3)
            for dy in [-0.4, 0.4]
        ])
        arrowsB_side = VGroup(*[
            Arrow(cupB_body.get_left() + UP * dy, cupB_body.get_left() + LEFT * 0.7 + UP * dy,
                  buff=0, color=HOT, stroke_width=3, max_tip_length_to_length_ratio=0.3)
            for dy in [-0.4, 0.4]
        ])
        cupA_arrows = VGroup(arrowsA, arrowsA_side)
        cupB_arrows = VGroup(arrowsB, arrowsB_side)

        e_lost_label = Text("Energy lost to surroundings", font_size=24, color=HOT).move_to(DOWN * 3.0)
        grav_ref = Arrow(UP * 3.2 + RIGHT * 5.8, UP * 2.4 + RIGHT * 5.8, buff=0, color=GRAY, stroke_width=3)

        # Bounce/rebound visuals for the "tight lid" beat
        bounce_dot = Dot(radius=0.08, color=HOT).move_to(cupA_liquid.get_top())
        contact_pt = lidA.get_center()
        bounce_up = ArcBetweenPoints(cupA_liquid.get_top(), lidA.get_center(), angle=-TAU / 8)
        bounce_down = ArcBetweenPoints(lidA.get_center(), cupA_liquid.get_top(), angle=-TAU / 8)
        rebound_arrow = Arrow(lidA.get_center(), lidA.get_center() + DOWN * 0.5 + LEFT * 0.3,
                               buff=0, color=COLD, stroke_width=3, max_tip_length_to_length_ratio=0.3)
        rebound_arrow2 = Arrow(lidA.get_center() + DOWN * 0.2, cupA_liquid.get_top(),
                                buff=0, color=COLD, stroke_width=3, max_tip_length_to_length_ratio=0.3)
        bounce_text = Text("Heat bounces back in!", font_size=24, color=COLD).next_to(cupA_body, LEFT, buff=0.6)

        # Gap / escape visuals for the "loose lid" beat (pre-positioned at lidB's FUTURE location
        # so they line up correctly once lidB shifts)
        lidB_shift_vec = UP * 0.35 + RIGHT * 0.45
        gap_region = Rectangle(width=0.4, height=0.15, color=HOT, stroke_width=2) \
            .move_to(lidB.get_center() + lidB_shift_vec + RIGHT * 0.6)
        escape_arrows = VGroup(*[
            Arrow(gap_region.get_center() + DOWN * 0.1 + RIGHT * dx, gap_region.get_center() + UP * 0.9 + RIGHT * dx,
                  buff=0, color=HOT, stroke_width=3, max_tip_length_to_length_ratio=0.3)
            for dx in [-0.15, 0.15]
        ])

        # Evaporation beat
        evap_title = Text("Evaporation", font_size=30, color=HOT).move_to(UP * 3.0)
        grav_tag = Arrow(cupB_body.get_top() + UP * 0.2, cupB_body.get_top() + UP * 1.0,
                          buff=0, color=GRAY, stroke_width=3)
        fastB = VGroup(*[Dot(radius=0.06, color=HOT).move_to(cupB_liquid.get_top()) for _ in range(4)])
        evap_paths = [
            ArcBetweenPoints(cupB_liquid.get_top(), cupB_liquid.get_top() + UP * 2.2 + RIGHT * dx, angle=-TAU / 10)
            for dx in [-0.6, -0.2, 0.2, 0.6]
        ]
        evap_label = Text("Loss of liquid mass & heat", font_size=24, color=HOT).move_to(DOWN * 3.0)

        vapor = VGroup(*[Dot(radius=0.06, color=COLD) for _ in range(2)])
        vapor[0].move_to(cupA_liquid.get_top() + LEFT * 0.2)
        vapor[1].move_to(cupA_liquid.get_top() + RIGHT * 0.2)
        vapor_path_up = ArcBetweenPoints(vapor[0].get_center(), lidA.get_center() + LEFT * 0.2, angle=-TAU / 10)
        vapor_path_up2 = ArcBetweenPoints(vapor[1].get_center(), lidA.get_center() + RIGHT * 0.2, angle=-TAU / 10)

        # Comparison bar chart beat
        left_val = ValueTracker(85.0)
        right_val = ValueTracker(85.0)
        left_column = Rectangle(width=1.2, height=3.0, color=COLD, fill_color=COLD, fill_opacity=0.4) \
            .move_to(LEFT * 2.5 + DOWN * 0.3)
        right_column = Rectangle(width=1.2, height=3.0, color=HOT, fill_color=HOT, fill_opacity=0.4) \
            .move_to(RIGHT * 2.5 + DOWN * 0.3)
        left_col_tag = Text("Tight Lid", font_size=24, color=COLD).next_to(left_column, UP, buff=0.2)
        right_col_tag = Text("Loose Lid", font_size=24, color=HOT).next_to(right_column, UP, buff=0.2)
        left_decimal = always_redraw(
            lambda: DecimalNumber(left_val.get_value(), num_decimal_places=1, unit="°C", font_size=28, color=COLD)
            .next_to(left_column, DOWN, buff=0.25)
        )
        right_decimal = always_redraw(
            lambda: DecimalNumber(right_val.get_value(), num_decimal_places=1, unit="°C", font_size=28, color=HOT)
            .next_to(right_column, DOWN, buff=0.25)
        )
        delta_text = Text("Smaller drop = better insulation", font_size=26, color=WHITE).move_to(DOWN * 3.0)

        # Final beat
        thermo_left = get_svg("thermometer", height=0.8).scale(2.0)
        thermo_right = get_svg("thermometer", height=0.8).scale(2.0)
        thermo_left.move_to(LEFT * 0.4 + DOWN * 0.4)
        thermo_right.move_to(RIGHT * 0.4 + DOWN * 0.4)
        final_line1 = Text("Choose your cup wisely.", font_size=32, color=WHITE).move_to(UP * 2.4)
        final_line2 = Text("A tight lid keeps the warmth in!", font_size=32, color=COLD).move_to(UP * 1.8)

        self.add(background)
        # ═══ PHASE 2: ANIMATIONS START HERE ═══

        with self.voiceover(text="How does the design of a cup affect how long your drink stays warm?") as tracker:
            sub = self.show_subtitle("How does the design of a cup affect how long your drink stays warm?")
            self.play(FadeIn(line1, shift=DOWN * 0.4), rate_func=smooth, run_time=1.2)
            self.play(FadeIn(line2, shift=UP * 0.35), rate_func=smooth, run_time=1.3)
            self.play(FadeIn(thermo_main, shift=LEFT * 0.6), rate_func=rush_from, run_time=1.3)
            self.play(FadeIn(temp_display), run_time=0.4, rate_func=smooth)
            self.play(Indicate(line2, color=HOT, scale_factor=1.12), run_time=0.9)
            self.wait(max(0.1, tracker.duration - 5.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Imagine two cups: one with a tight lid and one with a loose lid.") as tracker:
            sub = self.show_subtitle("Imagine two cups: one with a tight lid and one with a loose lid.")
            self.play(FadeOut(line1, shift=UP * 0.3), FadeOut(line2, shift=UP * 0.3),
                      thermo_main.animate.set_opacity(0.4), rate_func=rush_into, run_time=0.9)
            self.play(DrawBorderThenFill(cupA_body), DrawBorderThenFill(cupB_body),
                      rate_func=smooth, run_time=1.4)
            self.play(FadeIn(cupA_liquid, shift=UP * 0.3), FadeIn(cupB_liquid, shift=UP * 0.3),
                      rate_func=smooth, run_time=1.0)
            self.play(AnimationGroup(FadeIn(lidA, shift=DOWN * 0.5), FadeIn(lidB, shift=DOWN * 0.5),
                                     lag_ratio=0.3), rate_func=smooth, run_time=1.2)
            self.play(FadeIn(labelA, shift=UP * 0.2), FadeIn(labelB, shift=UP * 0.2),
                      rate_func=smooth, run_time=0.8)
            self.wait(max(0.1, tracker.duration - 5.7))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Inside, liquids are made of tiny particles that move around. In gases, these particles are far apart and move freely. In liquids, they're closer but still move.") as tracker:
            sub = self.show_subtitle("Liquids are made of tiny particles that move around.")
            self.play(AnimationGroup(*[GrowFromCenter(d) for d in dotsA], lag_ratio=0.15),
                      AnimationGroup(*[GrowFromCenter(d) for d in dotsB], lag_ratio=0.15),
                      rate_func=smooth, run_time=2.0)
            self.play(FadeIn(caption_heat, shift=UP * 0.2), rate_func=smooth, run_time=1.0)
            for _ in range(3):
                self.play(*[d.animate.shift(np.array([rng.uniform(-0.16, 0.16), rng.uniform(-0.16, 0.16), 0]))
                            for d in dotsA],
                          *[d.animate.shift(np.array([rng.uniform(-0.16, 0.16), rng.uniform(-0.16, 0.16), 0]))
                            for d in dotsB],
                          rate_func=there_and_back, run_time=1.1)
            self.wait(max(0.1, tracker.duration - 6.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Energy moves from warmer to cooler areas. This can happen through touching, moving fluids, or even through space.") as tracker:
            sub = self.show_subtitle("Energy moves from warmer to cooler areas.")
            self.play(FadeOut(caption_heat, shift=DOWN * 0.3), rate_func=rush_into, run_time=0.7)
            self.play(AnimationGroup(*[GrowArrow(a) for a in arrowsA], lag_ratio=0.2),
                      rate_func=smooth, run_time=1.6)
            self.play(AnimationGroup(*[GrowArrow(a) for a in arrowsB], lag_ratio=0.2),
                      rate_func=smooth, run_time=1.6)
            self.play(AnimationGroup(*[GrowArrow(a) for a in arrowsA_side],
                                     *[GrowArrow(a) for a in arrowsB_side], lag_ratio=0.2),
                      rate_func=smooth, run_time=1.2)
            self.play(FadeIn(e_lost_label, shift=UP * 0.2), GrowArrow(grav_ref),
                      rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 6.6))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="A cup with a tight lid keeps heat from escaping, so your drink stays warm longer.") as tracker:
            sub = self.show_subtitle("A tight lid keeps heat from escaping, so your drink stays warm longer.")
            self.play(FadeOut(e_lost_label, shift=UP * 0.2), FadeOut(grav_ref, shift=DOWN * 0.2),
                      VGroup(cupB, dotsB, cupB_arrows, labelB).animate.set_opacity(0.2),
                      rate_func=rush_into, run_time=1.0)
            self.play(FadeOut(arrowsA, shift=UP * 0.4), rate_func=rush_into, run_time=0.8)
            self.play(FadeIn(bounce_dot), rate_func=smooth, run_time=0.5)
            self.play(MoveAlongPath(bounce_dot, bounce_up), rate_func=rush_into, run_time=0.8)
            self.play(Flash(contact_pt, color=COLD, flash_radius=0.4),
                      GrowArrow(rebound_arrow), rate_func=smooth, run_time=0.9)
            self.play(MoveAlongPath(bounce_dot, bounce_down), GrowArrow(rebound_arrow2),
                      rate_func=smooth, run_time=1.0)
            self.play(FadeIn(bounce_text, shift=LEFT * 0.3), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 6.4))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="But a cup with a loose lid lets heat escape, cooling your drink faster.") as tracker:
            sub = self.show_subtitle("A loose lid lets heat escape, cooling your drink faster.")
            self.play(FadeOut(bounce_text, shift=RIGHT * 0.3), FadeOut(bounce_dot),
                      FadeOut(rebound_arrow), FadeOut(rebound_arrow2),
                      VGroup(cupA, dotsA, cupA_arrows, labelA).animate.set_opacity(0.2),
                      VGroup(cupB, dotsB, cupB_arrows, labelB).animate.set_opacity(1.0),
                      thermo_main.animate.set_opacity(1.0), rate_func=smooth, run_time=1.2)
            self.play(lidB.animate.shift(lidB_shift_vec).rotate(8 * DEGREES),
                      rate_func=smooth, run_time=1.0)
            self.play(Create(gap_region), rate_func=smooth, run_time=0.6)
            self.play(AnimationGroup(*[GrowArrow(a) for a in escape_arrows], lag_ratio=0.25),
                      rate_func=smooth, run_time=1.8)
            self.play(Indicate(gap_region, scale_factor=1.4, color=HOT), run_time=0.9)
            self.play(temp_tracker.animate.set_value(80.0), rate_func=linear, run_time=2.0)
            self.wait(max(0.1, tracker.duration - 7.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="If a cup is open, water molecules can escape into the air, causing evaporation.") as tracker:
            sub = self.show_subtitle("If a cup is open, water molecules escape into the air — evaporation.")
            self.play(FadeIn(evap_title, shift=DOWN * 0.3), FadeOut(gap_region),
                      rate_func=smooth, run_time=1.0)
            self.play(GrowArrow(grav_tag), rate_func=smooth, run_time=0.7)
            self.play(AnimationGroup(*[MoveAlongPath(d, p) for d, p in zip(fastB, evap_paths)],
                                     lag_ratio=0.25),
                      grav_tag.animate.shift(UP * 2.6 + RIGHT * 1.4),
                      rate_func=rush_from, run_time=2.2)
            self.play(FadeOut(fastB, shift=UP * 0.4), FadeOut(grav_tag),
                      rate_func=rush_into, run_time=0.8)
            self.play(dotsB.animate.set_color(ManimColor("#B06A3B")),
                      temp_tracker.animate.set_value(62.0), rate_func=smooth, run_time=2.2)
            self.play(FadeIn(evap_label, shift=UP * 0.2), rate_func=smooth, run_time=1.0)
            self.wait(max(0.1, tracker.duration - 8.0))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="A closed cup prevents this, keeping the liquid inside.") as tracker:
            sub = self.show_subtitle("A closed cup prevents this, keeping the liquid inside.")
            self.play(FadeOut(evap_title, shift=UP * 0.3), FadeOut(evap_label, shift=DOWN * 0.3),
                      FadeOut(escape_arrows, shift=UP * 0.4),
                      VGroup(cupB, dotsB, cupB_arrows, labelB).animate.set_opacity(0.2),
                      VGroup(cupA, dotsA, labelA).animate.set_opacity(1.0),
                      rate_func=smooth, run_time=1.2)
            self.play(AnimationGroup(*[FadeIn(d, shift=UP * 0.2) for d in vapor], lag_ratio=0.25),
                      rate_func=smooth, run_time=1.6)
            self.play(MoveAlongPath(vapor[0], vapor_path_up), MoveAlongPath(vapor[1], vapor_path_up2),
                      rate_func=there_and_back, run_time=1.6)
            self.play(Circumscribe(lidA, color=COLD), run_time=1.2)
            self.play(FadeIn(thermo_sealed, shift=RIGHT * 0.4), FadeIn(sealed_tag),
                      rate_func=smooth, run_time=1.0)
            self.play(FadeIn(sealed_display), run_time=0.4, rate_func=smooth)
            self.play(sealed_tracker.animate.set_value(78.0), FadeIn(no_escape_text, shift=UP * 0.2),
                      rate_func=smooth, run_time=2.2)
            self.wait(max(0.1, tracker.duration - 8.8))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="So, a cup with a tight lid keeps liquids warmer longer and reduces evaporation.") as tracker:
            sub = self.show_subtitle("A tight lid keeps liquids warmer longer and reduces evaporation.")
            temp_display.clear_updaters()
            sealed_display.clear_updaters()
            self.play(FadeOut(VGroup(cupA, cupB, dotsA, dotsB, labelA, labelB, vapor,
                                     cupA_arrows, cupB_arrows, no_escape_text, sealed_tag), shift=DOWN * 0.3),
                      FadeOut(thermo_main), FadeOut(thermo_sealed),
                      FadeOut(temp_display), FadeOut(sealed_display),
                      rate_func=rush_into, run_time=1.3)
            self.play(FadeIn(left_column, shift=UP * 0.3), FadeIn(right_column, shift=UP * 0.3),
                      FadeIn(left_col_tag, shift=UP * 0.2), FadeIn(right_col_tag, shift=UP * 0.2),
                      rate_func=smooth, run_time=1.2)
            self.play(FadeIn(left_decimal), FadeIn(right_decimal), run_time=0.4, rate_func=smooth)
            self.play(left_val.animate.set_value(71.4), right_val.animate.set_value(54.8),
                      rate_func=smooth, run_time=2.0)
            self.play(Circumscribe(left_column, color=COLD, buff=0.25), run_time=1.2)
            self.play(Circumscribe(right_column, color=HOT, buff=0.25), run_time=1.2)
            self.play(Flash(left_decimal, color=COLD, flash_radius=0.9), run_time=0.8)
            self.play(FadeIn(delta_text, shift=UP * 0.2), rate_func=smooth, run_time=1.2)
            self.play(Indicate(delta_text, color=YELLOW, scale_factor=1.25), run_time=0.9)
            self.wait(max(0.1, tracker.duration - 10.5))
            self.play(FadeOut(sub), run_time=0.4)

        with self.voiceover(text="Next time you choose a cup, think about how its design affects your drink!") as tracker:
            sub = self.show_subtitle("Next time you choose a cup, think about how its design affects your drink!")
            left_decimal.clear_updaters()
            right_decimal.clear_updaters()
            self.play(FadeOut(delta_text, shift=DOWN * 0.3), FadeOut(left_decimal, shift=DOWN * 0.3),
                      FadeOut(right_decimal, shift=DOWN * 0.3), FadeOut(left_col_tag), FadeOut(right_col_tag),
                      FadeOut(left_column), FadeOut(right_column),
                      FadeIn(thermo_left, shift=LEFT * 0.3), FadeIn(thermo_right, shift=RIGHT * 0.3),
                      rate_func=rush_into, run_time=1.2)
            self.play(thermo_left.animate.move_to(LEFT * 2.0 + DOWN * 0.4).scale(0.85),
                      thermo_right.animate.move_to(RIGHT * 2.0 + DOWN * 0.4).scale(0.85),
                      rate_func=smooth, run_time=1.5)
            self.play(FadeIn(final_line1, shift=UP * 0.3), rate_func=smooth, run_time=1.2)
            self.play(FadeIn(final_line2, shift=UP * 0.3), rate_func=smooth, run_time=1.4)
            self.wait(max(0.1, tracker.duration - 6.0))
            self.play(FadeOut(sub), run_time=0.4)

        self.play(FadeOut(VGroup(final_line1, final_line2, thermo_left, thermo_right), shift=DOWN * 0.3),
                  rate_func=rush_into, run_time=1.5)