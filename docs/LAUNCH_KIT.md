# Automated Recompilers — Launch & Promotion Kit

A public demo and a reproducible native result give people a reason to explore the project and follow its progress. The project is a prototype: commercial game playability, accurate graphics, and host audio remain unfinished.

## Start with these links

- Browser demo: https://yefan911.github.io/automated-recompilers/
- Repository: https://github.com/yefan911/automated-recompilers
- Native homebrew walkthrough: https://github.com/yefan911/automated-recompilers#quick-start-in-60-seconds
- Roadmap: https://github.com/yefan911/automated-recompilers/blob/main/ROADMAP.md
- Contributor tasks: https://github.com/yefan911/automated-recompilers/blob/main/docs/CONTRIBUTOR_BOUNTIES.md
- Share image: https://yefan911.github.io/automated-recompilers/demo/social-preview.png

## Launch sequence

1. Keep the main branch CI green and verify that the hosted demo works on desktop and mobile. Show the bundled homebrew framebuffer and link the commands that reproduce it.
2. Publish one technical walkthrough: why MIPS branch predicates must be captured before delay-slot execution, or how ARM/Thumb state affects CFG discovery. Include a short instruction example and a link to its native regression test.
3. Share that walkthrough with one relevant community at a time. Respond to technical questions and record useful feedback as roadmap work. Check each community's current submission and self-promotion rules before posting.
4. Publish a follow-up when a visible milestone lands, such as continuous studio framebuffer streaming or verified affine rendering. Show the before/after behavior and reproduction steps.
5. Review GitHub traffic weekly: unique visitors, referring sites, clones, new stars, and contributions. Compare with the initial **19 stars on 2026-11-07**. Favor channels that bring useful technical feedback and contributors.

## What the current traffic suggests

GitHub's rolling 14-day snapshot on 2026-11-07 reports **331 repository views / 211 unique visitors** and **985 clones / 222 unique cloners**. Clone counts can include automation. Recorded referrals are led by `reddit.com` (**106 views / 82 uniques**) and the Reddit app (**57 / 45**), followed by GitHub (**5 / 5**). Unique visitors can overlap across referrers.

The repository overview accounts for **280 views / 209 uniques**, while the beta release page has **5 views / 5 uniques**. Prioritize the README's direct demo and reproduction links, then share a technical progress update with the Reddit audience already finding the project. Use HN as an additional experiment once the demo is live and you can answer questions. These counts describe repository traffic, not GitHub Pages visits or star conversion.

## Show HN

Use the live demo as the submission URL. [Show HN guidance](https://news.ycombinator.com/showhn.html) asks for something people can try; the browser playground and bundled homebrew provide that entry point.

**Title:** Show HN: Experimental ROM-to-C recompiler with a GBA homebrew demo

**URL:** https://yefan911.github.io/automated-recompilers/

**Opening comment:**

> I am building an experimental static recompilation framework for GBA, N64, PS1, and SNES. It follows control flow from ROM entry points, lowers selected instructions into C, and invokes a host compiler.
>
> The bundled GBA homebrew runs as a native executable, initializes Mode 3, and writes 2,400 pixels. The README shows how to capture its 240×160 framebuffer. The browser page includes a generated CFG and small JavaScript instruction examples; it does not run the full Python recompiler.
>
> CPU and hardware support are partial. Commercial game playability, accurate graphics, and host audio are still roadmap work.
>
> I would appreciate feedback on indirect control flow, CPU-state-dependent CFG variants, and tests that execute generated C. Source and instructions: https://github.com/yefan911/automated-recompilers

## Compiler and reverse-engineering communities

For [Lobsters](https://lobste.rs/) or a relevant [r/ReverseEngineering](https://www.reddit.com/r/ReverseEngineering/) thread, lead with a specific engineering result and link to the code. Use a community account and follow its current rules.

**Title:** Capturing MIPS branch state before delay slots in a ROM-to-C prototype

**Draft:**

> A MIPS delay-slot instruction can change the register used by a branch or indirect jump. Our generated C now captures the predicate or target before executing the slot, while making call link registers visible to the slot.
>
> Native regression tests compile and execute examples where the slot changes a branch operand, clears a JR/JALR target, or reads the link register.
>
> The framework also has prototype ARM/Thumb and 65816 lifters. A bundled GBA homebrew provides a reproducible native framebuffer result; commercial game compatibility remains unfinished.
>
> Code and tests: https://github.com/yefan911/automated-recompilers/blob/main/tests/test_mips_semantics.py
>
> Demo: https://yefan911.github.io/automated-recompilers/

## Social post

> ROM → control flow graph → native C.
>
> Explore our experimental GBA/N64/PS1/SNES recompiler and its bundled GBA homebrew result. CPU and hardware support are still partial.
>
> Try it: https://yefan911.github.io/automated-recompilers/
>
> Source: https://github.com/yefan911/automated-recompilers

Attach `docs/demo/social-preview.png` or the existing terminal walkthrough GIF. For Bluesky, split the demo and source into two short posts if needed. Keep a single clear link in the first post.

## Contributor discovery

Link newcomers to a small, currently missing instruction or a visual regression task with its expected result and test command. Check the bounty catalog against the current lifter before recommending an opcode. Submit to curated recompilation lists only when the project fits their inclusion rules, and describe its prototype status.

Use stars as a signal of interest. Good documentation, working examples, useful releases, and responsive technical discussion are the ongoing work that makes following the repository worthwhile.
