from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.azure import AzureService
import numpy as np

import urllib.request, os as _os


def get_svg(name, url, height=0.8):
    """Download SVG from R2 and return as a sized SVGMobject."""
    tmp = f"/tmp/svg_{name}.svg"
    if not _os.path.exists(tmp):
        urllib.request.urlretrieve(url, tmp)
    return SVGMobject(tmp).set_height(height)


class ThermodynamicsScene(VoiceoverScene):

    def show_subtitle(self, text, duration=None):
        import textwrap
        wrapped = "\n".join(textwrap.wrap(text, width=70))
        subtitle = Text(wrapped, font_size=18, color=WHITE, line_spacing=1.2).to_edge(DOWN, buff=0.3)
        self.play(FadeIn(subtitle))
        if duration:
            self.wait(duration)
        return subtitle

    def construct(self):
        self.set_speech_service(AzureService(voice="en-US-JennyNeural", global_speed=0.90))

        # ══════════════════════════════════════════════════════════════════════
        # SETUP — every mobject defined before the first animation
        # ══════════════════════════════════════════════════════════════════════

        steam_color = GRAY_B

        # ── Coffee cup (built from basic shapes) ──────────────────────────────
        cup_body = Polygon(
            np.array([-0.45, -0.55, 0]),
            np.array([ 0.45, -0.55, 0]),
            np.array([ 0.60,  0.45, 0]),
            np.array([-0.60,  0.45, 0]),
            color=WHITE, stroke_width=2,
            fill_color="#6F4E37", fill_opacity=1.0,
        )
        cup_handle = Arc(
            radius=0.28, start_angle=-PI / 2, angle=PI,
            color=WHITE, stroke_width=3,
        )
        cup_handle.next_to(cup_body, RIGHT, buff=-0.08).shift(DOWN * 0.05)

        cup_saucer = Ellipse(
            width=1.4, height=0.18,
            color=WHITE, fill_color=GRAY_C, fill_opacity=1.0,
        )
        cup_saucer.next_to(cup_body, DOWN, buff=-0.12)

        cup_surface = Ellipse(
            width=1.0, height=0.14,
            color="#4a1a00", fill_color="#4a1a00", fill_opacity=1.0,
        )
        cup_surface.move_to(cup_body.get_top() + DOWN * 0.15)

        cup = VGroup(cup_saucer, cup_body, cup_handle, cup_surface)
        cup.move_to(ORIGIN)

        cup_top_pos = cup_body.get_top() + np.array([0, 0.05, 0])

        # ── Steam curves ──────────────────────────────────────────────────────
        def make_steam(x_offset, curve_dir):
            p0 = cup_top_pos + np.array([x_offset,                    0.0, 0])
            p1 = cup_top_pos + np.array([x_offset + curve_dir * 0.2,  0.5, 0])
            p2 = cup_top_pos + np.array([x_offset - curve_dir * 0.2,  1.0, 0])
            p3 = cup_top_pos + np.array([x_offset + curve_dir * 0.1,  1.5, 0])
            return CubicBezier(p0, p1, p2, p3, color=steam_color, stroke_width=2.5)

        steam1      = make_steam(-0.25,  1)
        steam2      = make_steam( 0.00, -1)
        steam3      = make_steam( 0.25,  1)
        steam_lines = VGroup(steam1, steam2, steam3)

        # ── Title ─────────────────────────────────────────────────────────────
        title = Text("Thermodynamics", font_size=44, color=YELLOW)
        title.to_edge(UP, buff=0.5)
        underline = Line(
            title.get_left(), title.get_right(),
            color=YELLOW, stroke_width=2,
        )
        underline.next_to(title, DOWN, buff=0.1)

        # ── System / Surroundings diagram ─────────────────────────────────────
        surroundings_rect = Rectangle(
            width=6.5, height=3.8, color=BLUE_B, stroke_width=2,
        )
        surroundings_rect.move_to(ORIGIN)

        surroundings_label = Text("Surroundings", font_size=22, color=BLUE_B)
        surroundings_label.move_to(
            surroundings_rect.get_corner(UL) + np.array([0.9, -0.35, 0])
        )

        system_rect = Rectangle(
            width=2.2, height=1.8, color=ORANGE, stroke_width=3,
            fill_color=ORANGE, fill_opacity=0.12,
        )
        system_rect.move_to(ORIGIN)

        system_label = Text("System\n(coffee)", font_size=20, color=ORANGE)
        system_label.move_to(system_rect.get_center())

        # ── Energy arrows ─────────────────────────────────────────────────────
        heat_arrow = Arrow(
            system_rect.get_right(),
            system_rect.get_right() + RIGHT * 1.6,
            color=RED, buff=0.05, stroke_width=4,
        )
        q_label = MathTex("Q", font_size=28, color=RED)
        q_label.next_to(heat_arrow, UP, buff=0.1)

        work_arrow_in = Arrow(
            system_rect.get_left() + LEFT * 1.6,
            system_rect.get_left(),
            color=GREEN, buff=0.05, stroke_width=4,
        )
        win_label = MathTex("W_{in}", font_size=24, color=GREEN)
        win_label.next_to(work_arrow_in, UP, buff=0.1)

        work_arrow_out = Arrow(
            system_rect.get_bottom(),
            system_rect.get_bottom() + DOWN * 0.9,
            color=PURPLE, buff=0.05, stroke_width=4,
        )
        wout_label = MathTex("W_{out}", font_size=24, color=PURPLE)
        wout_label.next_to(work_arrow_out, RIGHT, buff=0.1)

        diagram_group = VGroup(
            surroundings_rect, surroundings_label,
            system_rect, system_label,
            heat_arrow, q_label,
            work_arrow_in, win_label,
            work_arrow_out, wout_label,
        )

        # ── First Law ─────────────────────────────────────────────────────────
        first_law_tex = MathTex(r"\Delta U = Q - W", font_size=52)
        first_law_tex.move_to(DOWN * 1.8)
        formula_box = SurroundingRectangle(first_law_tex, color=YELLOW, buff=0.2)

        # ── Energy bars ───────────────────────────────────────────────────────
        bar_base_y = -0.8

        bar_U_bg = Rectangle(width=0.9, height=2.0,
                             color=GRAY, fill_color=GRAY, fill_opacity=0.15)
        bar_U_bg.move_to(np.array([-2.2, bar_base_y, 0]))

        bar_Q_bg = Rectangle(width=0.9, height=2.0,
                             color=GRAY, fill_color=GRAY, fill_opacity=0.15)
        bar_Q_bg.move_to(np.array([0.0, bar_base_y, 0]))

        bar_W_bg = Rectangle(width=0.9, height=2.0,
                             color=GRAY, fill_color=GRAY, fill_opacity=0.15)
        bar_W_bg.move_to(np.array([2.2, bar_base_y, 0]))

        bar_U = Rectangle(width=0.8, height=1.4,
                          color=BLUE, fill_color=BLUE, fill_opacity=0.85)
        bar_U.align_to(bar_U_bg, DOWN).shift(UP * 0.05)

        bar_Q = Rectangle(width=0.8, height=0.9,
                          color=RED, fill_color=RED, fill_opacity=0.85)
        bar_Q.align_to(bar_Q_bg, DOWN).shift(UP * 0.05)

        bar_W = Rectangle(width=0.8, height=0.5,
                          color=GREEN, fill_color=GREEN, fill_opacity=0.85)
        bar_W.align_to(bar_W_bg, DOWN).shift(UP * 0.05)

        lbl_U = MathTex(r"\Delta U", font_size=26, color=BLUE)
        lbl_U.next_to(bar_U_bg, DOWN, buff=0.15)
        lbl_Q = MathTex("Q", font_size=26, color=RED)
        lbl_Q.next_to(bar_Q_bg, DOWN, buff=0.15)
        lbl_W = MathTex("W", font_size=26, color=GREEN)
        lbl_W.next_to(bar_W_bg, DOWN, buff=0.15)

        # ── Second Law ────────────────────────────────────────────────────────
        second_law_text = Text(
            "Second Law of Thermodynamics", font_size=32, color=ORANGE,
        )
        second_law_text.move_to(UP * 1.8)

        entropy_formula = MathTex(r"\Delta S \geq 0", font_size=56, color=YELLOW)
        entropy_formula.move_to(UP * 0.3)

        entropy_desc = Text(
            "Entropy always increases in an isolated system",
            font_size=24, color=GRAY_A,
        )
        entropy_desc.move_to(DOWN * 1.0)

        # ── Hot / Cold circles ────────────────────────────────────────────────
        hot_circle = Circle(radius=0.8, color=RED, fill_color=RED, fill_opacity=0.5)
        hot_circle.move_to(LEFT * 2.8)
        hot_label = Text("Hot\n800 K", font_size=22, color=WHITE)
        hot_label.move_to(hot_circle.get_center())

        cold_circle = Circle(radius=0.8, color=BLUE, fill_color=BLUE, fill_opacity=0.5)
        cold_circle.move_to(RIGHT * 2.8)
        cold_label = Text("Cold\n300 K", font_size=22, color=WHITE)
        cold_label.move_to(cold_circle.get_center())

        flow_arrow = Arrow(
            hot_circle.get_right(), cold_circle.get_left(),
            color=YELLOW, buff=0.1,
        )
        flow_label = Text("Heat Flow", font_size=22, color=YELLOW)
        flow_label.next_to(flow_arrow, UP, buff=0.15)

        # ── Third Law ─────────────────────────────────────────────────────────
        third_law_text = Text(
            "Third Law of Thermodynamics", font_size=32, color=TEAL,
        )
        third_law_text.move_to(UP * 2.2)

        third_formula = MathTex(
            r"S \rightarrow 0 \text{ as } T \rightarrow 0\,\text{K}",
            font_size=44, color=YELLOW,
        )
        third_formula.move_to(UP * 0.9)

        crystal_label = Text(
            "Perfect crystal at absolute zero", font_size=24, color=TEAL_B,
        )
        crystal_label.move_to(DOWN * 0.1)

        crystal_dots = VGroup(*[
            Dot(
                point=np.array([(col - 3) * 0.5, row * 0.4 - 1.6, 0]),
                radius=0.07, color=TEAL_A,
            )
            for row in range(3)
            for col in range(7)
        ])

        # ── Summary ───────────────────────────────────────────────────────────
        result_text = Text(
            "The Three Laws of Thermodynamics", font_size=36, color=YELLOW,
        )
        result_text.to_edge(UP, buff=0.5)

        laws_summary = VGroup(
            Text("1st Law:  Energy is conserved  —  ΔU = Q − W",
                 font_size=22, color=WHITE),
            Text("2nd Law:  Entropy always increases  —  ΔS ≥ 0",
                 font_size=22, color=WHITE),
            Text("3rd Law:  S → 0  as  T → 0 K",
                 font_size=22, color=WHITE),
        )
        laws_summary.arrange(DOWN, aligned_edge=LEFT, buff=0.45)
        laws_summary.move_to(ORIGIN + DOWN * 0.3)

        # ── Final cup ─────────────────────────────────────────────────────────
        final_cup = cup.copy()
        final_cup.move_to(UP * 0.5)

        thermo_label = Text("Thermodynamics in Action!", font_size=36, color=YELLOW)
        thermo_label.next_to(final_cup, DOWN, buff=0.5)

        # ══════════════════════════════════════════════════════════════════════
        # ANIMATIONS — original beats, unchanged
        # ══════════════════════════════════════════════════════════════════════

        # ── BEAT 1: Cup of coffee appears ──────────────────────────────
        with self.voiceover(text="Imagine a steaming cup of coffee sitting on your table.") as tracker:
            sub = self.show_subtitle("Imagine a steaming cup of coffee sitting on your table.")

            self.play(FadeIn(cup, shift=UP * 0.4, rate_func=smooth), run_time=0.8)
            self.play(cup.animate.shift(UP * 0.08), run_time=0.4, rate_func=smooth)
            self.play(cup.animate.shift(DOWN * 0.08), run_time=0.4, rate_func=smooth)
            self.wait(max(0.1, tracker.duration - 2.0))
        self.play(FadeOut(sub))

        # ── BEAT 2: Steam dissipates ────────────────────────────────────
        with self.voiceover(text="Over time, it cools down. But why does this happen?") as tracker:
            sub = self.show_subtitle("Over time, it cools down. But why does this happen?")

            self.play(
                AnimationGroup(Create(steam1), Create(steam2), Create(steam3), lag_ratio=0.25),
                run_time=1.0,
            )
            self.play(FadeOut(steam_lines, shift=UP * 0.6, rate_func=smooth), run_time=0.8)
            self.wait(max(0.1, tracker.duration - 2.0))
        self.play(FadeOut(sub))

        # ── BEAT 3: Question mark appears ──────────────────────────────
        with self.voiceover(text="") as tracker:
            sub = self.show_subtitle("")
            question_mark = Tex("?", font_size=80, color=YELLOW)
            question_mark.move_to(cup.get_top() + UP * 1.0)
            self.play(DrawBorderThenFill(question_mark), run_time=0.8)
            self.play(Indicate(question_mark, scale_factor=1.3, color=YELLOW), run_time=0.6)
            self.wait(max(0.1, tracker.duration - 0.1))
        self.play(FadeOut(sub))

        # ── BEAT 4: Thermodynamics title appears ────────────────────────
        with self.voiceover(text="Welcome to the world of thermodynamics, where we explore the dance of energy, heat, and work.") as tracker:
            sub = self.show_subtitle("Welcome to the world of thermodynamics — the dance of energy, heat, and work.")

            self.play(
                AnimationGroup(
                    cup.animate.shift(LEFT * 4.5),
                    question_mark.animate.shift(LEFT * 4.5),
                    lag_ratio=0.0,
                ),
                run_time=0.7, rate_func=smooth,
            )
            self.play(FadeIn(title, shift=DOWN * 0.5), run_time=0.8)
            self.play(GrowFromEdge(underline, edge=LEFT), run_time=0.5)
            self.wait(max(0.1, tracker.duration - 2.5))
        self.play(FadeOut(sub))
        self.play(FadeOut(cup), FadeOut(question_mark))

        # ── BEAT 5: System and Surroundings diagram ─────────────────────
        with self.voiceover(text="Let's break it down.") as tracker:
            sub = self.show_subtitle("Let's break it down.")

            self.play(
                AnimationGroup(Create(surroundings_rect), Create(system_rect), lag_ratio=0.25),
                run_time=1.2,
            )
            self.play(
                AnimationGroup(Write(system_label), Write(surroundings_label), lag_ratio=0.3),
                run_time=0.8,
            )
            self.wait(max(0.1, tracker.duration - 2.5))
        self.play(FadeOut(sub))

        # ── BEAT 6: System highlighted ──────────────────────────────────
        with self.voiceover(text="First, we define our system: the coffee. Everything else is the surroundings.") as tracker:
            sub = self.show_subtitle("First, we define our system: the coffee. Everything else is the surroundings.")

            glow = system_rect.copy().set_stroke(BLUE, width=10).set_opacity(0.35)
            self.play(system_rect.animate.set_stroke(BLUE, width=6), run_time=0.4)
            self.play(
                AnimationGroup(FadeIn(glow, run_time=0.4), FadeOut(glow, run_time=0.6))
            )
            self.play(
                system_rect.animate.shift(LEFT * 0.3).scale(1.06),
                system_label.animate.shift(LEFT * 0.3).scale(1.06),
                run_time=0.5, rate_func=smooth,
            )
            self.play(
                system_rect.animate.shift(RIGHT * 0.3).scale(1 / 1.06),
                system_label.animate.shift(RIGHT * 0.3).scale(1 / 1.06),
                run_time=0.5, rate_func=smooth,
            )
            self.wait(max(0.1, tracker.duration - 2.5))
        self.play(FadeOut(sub))

        # ── BEAT 7: Energy arrows appear ────────────────────────────────
        with self.voiceover(text="Energy flows from the coffee to the air, seeking balance.") as tracker:
            sub = self.show_subtitle("Energy flows from the coffee to the air, seeking balance.")

            self.play(
                AnimationGroup(
                    GrowArrow(heat_arrow),
                    GrowArrow(work_arrow_in),
                    GrowArrow(work_arrow_out),
                    lag_ratio=0.25,
                ),
                run_time=1.2,
            )
            self.play(
                AnimationGroup(Write(q_label), Write(win_label), Write(wout_label), lag_ratio=0.2),
                run_time=0.7,
            )
            self.wait(max(0.1, tracker.duration - 2.5))
        self.play(FadeOut(sub))

        # ── BEAT 8: First Law formula ────────────────────────────────────
        with self.voiceover(text="The First Law of Thermodynamics tells us energy can't be created or destroyed, only transformed.") as tracker:
            sub = self.show_subtitle("The First Law: energy can't be created or destroyed, only transformed.")

            self.play(
                diagram_group.animate.shift(UP * 0.5),
                run_time=0.5, rate_func=smooth,
            )
            self.play(Write(first_law_tex), run_time=1.1)
            self.play(Create(formula_box), run_time=0.5)
            self.wait(max(0.1, tracker.duration - 2.5))
        self.play(FadeOut(sub))

        # ── BEAT 9: Energy transformation visual ────────────────────────
        with self.voiceover(text="As the coffee cools, energy is transferred as heat.") as tracker:
            sub = self.show_subtitle("As the coffee cools, energy is transferred as heat.")

            self.play(diagram_group.animate.set_opacity(0.3), run_time=0.5)
            self.play(
                FadeIn(bar_U_bg), FadeIn(bar_Q_bg), FadeIn(bar_W_bg),
                run_time=0.3,
            )
            self.play(
                AnimationGroup(
                    GrowFromEdge(bar_U, DOWN),
                    GrowFromEdge(bar_Q, DOWN),
                    GrowFromEdge(bar_W, DOWN),
                    lag_ratio=0.25,
                ),
                run_time=1.0,
            )
            self.play(
                AnimationGroup(Write(lbl_U), Write(lbl_Q), Write(lbl_W), lag_ratio=0.2),
                run_time=0.6,
            )
            self.wait(max(0.1, tracker.duration - 2.5))

            bars_group = VGroup(
                bar_U_bg, bar_Q_bg, bar_W_bg,
                bar_U, bar_Q, bar_W,
                lbl_U, lbl_Q, lbl_W,
            )
        self.play(FadeOut(sub))

        # ── BEAT 10: Second Law concept ─────────────────────────────────
        with self.voiceover(text="The Second Law introduces entropy, the universe's tendency towards disorder.") as tracker:
            sub = self.show_subtitle("The Second Law introduces entropy — the universe's tendency towards disorder.")

            self.play(
                FadeOut(bars_group),
                FadeOut(first_law_tex),
                FadeOut(formula_box),
                diagram_group.animate.set_opacity(0.15),
                run_time=0.6,
            )
            self.play(Write(second_law_text), run_time=0.8)
            self.play(Write(entropy_formula), run_time=0.7)
            self.play(FadeIn(entropy_desc, shift=UP * 0.2), run_time=0.6)
            self.wait(max(0.1, tracker.duration - 2.5))
        self.play(FadeOut(sub))

        # ── BEAT 11: Entropy increase visual ───────────────────────────
        with self.voiceover(text="This is why heat flows naturally from hot to cold.") as tracker:
            sub = self.show_subtitle("This is why heat flows naturally from hot to cold.")

            self.play(
                FadeOut(second_law_text),
                FadeOut(entropy_formula),
                FadeOut(entropy_desc),
                run_time=0.4,
            )
            self.play(
                AnimationGroup(FadeIn(hot_circle), FadeIn(hot_label), lag_ratio=0.1),
                AnimationGroup(FadeIn(cold_circle), FadeIn(cold_label), lag_ratio=0.1),
                run_time=0.6,
            )
            self.play(GrowArrow(flow_arrow), Write(flow_label), run_time=0.8)
            self.wait(max(0.1, tracker.duration - 2.5))

            heat_flow_group = VGroup(
                hot_circle, hot_label, cold_circle, cold_label, flow_arrow, flow_label,
            )
        self.play(FadeOut(sub))

        # ── BEAT 12: Third Law concept ──────────────────────────────────
        with self.voiceover(text="And as we approach absolute zero, entropy approaches zero too.") as tracker:
            sub = self.show_subtitle("And as we approach absolute zero, entropy approaches zero too.")

            self.play(FadeOut(heat_flow_group), run_time=0.4)
            self.play(Write(third_law_text), run_time=0.7)
            self.play(Write(third_formula), run_time=0.8)
            self.wait(max(0.1, tracker.duration - 2.0))
        self.play(FadeOut(sub))

        # ── BEAT 13: Crystal structure visual ──────────────────────────
        with self.voiceover(text="") as tracker:
            sub = self.show_subtitle("")

            self.play(FadeIn(crystal_label, shift=UP * 0.2), run_time=0.5)
            self.play(
                AnimationGroup(*[FadeIn(d, scale=0.5) for d in crystal_dots], lag_ratio=0.05),
                run_time=0.8,
            )
            self.wait(max(0.1, tracker.duration - 0.1))

            third_group = VGroup(third_law_text, third_formula, crystal_label, crystal_dots)
        self.play(FadeOut(sub))

        # ── BEAT 14: Result shown ───────────────────────────────────────
        with self.voiceover(text="So, the cooling coffee isn't just a mundane event; it's a glimpse into the fundamental laws of nature.") as tracker:
            sub = self.show_subtitle("So, the cooling coffee isn't just a mundane event — it's a glimpse into the fundamental laws of nature.")

            self.play(FadeOut(third_group), FadeOut(diagram_group), run_time=0.5)
            self.play(FadeIn(result_text, shift=UP * 0.3), run_time=0.8)
            self.play(
                AnimationGroup(
                    *[FadeIn(law, shift=RIGHT * 0.3) for law in laws_summary],
                    lag_ratio=0.3,
                ),
                run_time=1.0,
            )
            self.play(Circumscribe(result_text, color=YELLOW), run_time=0.8)
            self.wait(max(0.1, tracker.duration - 3.0))
        self.play(FadeOut(sub))

        # ── BEAT 15: Callback to coffee cooling ─────────────────────────
        with self.voiceover(text="Next time you sip your coffee, remember, you're witnessing thermodynamics in action.") as tracker:
            sub = self.show_subtitle("Next time you sip your coffee, remember — you're witnessing thermodynamics in action.")

            self.play(FadeOut(result_text), FadeOut(laws_summary), run_time=0.4)
            self.play(FadeIn(final_cup, shift=UP * 0.3), run_time=0.7)
            self.play(Write(thermo_label), run_time=0.7)
            self.play(
                Indicate(thermo_label, scale_factor=1.2, color=YELLOW),
                final_cup.animate.shift(UP * 0.1),
                run_time=0.6,
            )
            self.play(final_cup.animate.shift(DOWN * 0.1), run_time=0.3)
            self.wait(max(0.1, tracker.duration - 3.0))
        self.play(FadeOut(sub))

        # Final fade
        self.play(
            FadeOut(title), FadeOut(underline),
            FadeOut(final_cup), FadeOut(thermo_label),
            run_time=1.0,
        )
