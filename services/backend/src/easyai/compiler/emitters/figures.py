"""Figure statements use explicit Figure/Axes objects and bounded sample selection."""

from typing import Literal

from easyai.compiler.source_map import CodeWriter
from easyai.domain.contracts import Origin
from easyai.domain.program import FigureSpec, NormalizeStep, ProgramIR


def emit_figures(
    w: CodeWriter,
    program: ProgramIR,
    figures: list[FigureSpec],
    phase: str,
    indent: str,
) -> None:
    for figure in figures:

        def line(
            text: str,
            origin: Origin = figure.origin,
            kind: Literal["semantic", "scaffold"] = "semantic",
        ) -> None:
            w.line(indent + text, origin, kind)

        epoch = "epoch" if phase == "epoch_end" else "None"
        sizes = {"small": (6, 4), "medium": (10, 6), "large": (14, 8)}
        line("context.check_cancelled()")
        line(f"fig = plt.figure(figsize={sizes[figure.size]!r}, dpi=100)")
        line("try:", kind="scaffold")
        line(f"    grid = fig.add_gridspec({figure.layout[0]}, {figure.layout[1]})")
        contributors: list[str] = []
        for index, panel in enumerate(figure.panels):
            contributors.append(panel.origin.block_id)
            origin = panel.origin
            line(f"    ax = fig.add_subplot(grid[{index}])", origin)
            if panel.title is not None:
                contributors.append(panel.title.origin.block_id)
                line(
                    f"    ax.set_title({panel.title.text!r}, color={panel.title.color!r})",
                    panel.title.origin,
                )
            if panel.chart_type in {"line", "scatter"}:
                for source in panel.sources:
                    contributors.append(source.origin.block_id)
                    history = source.source + "_history"
                    label = (
                        "Training loss"
                        if source.source == "train_loss"
                        else "Test accuracy (fraction)"
                    )
                    line(
                        f"    ax.{'plot' if panel.chart_type == 'line' else 'scatter'}(epoch_history, {history}, label={label!r})",
                        source.origin,
                    )
                line("    ax.set_xlabel('Epoch')", origin)
                labels = {source.source for source in panel.sources}
                if labels == {"test_accuracy"}:
                    line("    ax.set_ylabel('Test accuracy (%)')", origin)
                    line("    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))", origin)
                elif labels == {"train_loss"}:
                    line("    ax.set_ylabel('Cross entropy loss')", origin)
                else:
                    line("    ax.set_ylabel('Loss / accuracy (fraction; different units)')", origin)
            else:
                source = panel.sources[0]
                contributors.extend(s.origin.block_id for s in panel.sources)
                role = "train" if source.source == "train_samples" else "test"
                loader_id = (
                    program.training.train_loader_id
                    if role == "train"
                    else program.training.test_loader_id
                )
                loader = next(item for item in program.dataloaders if item.id == loader_id)
                dataset = next(item for item in program.datasets if item.id == loader.dataset_id)
                transform = next(
                    item for item in program.transforms if item.id == dataset.transform_id
                )
                normalize = next(
                    (step for step in transform.steps if isinstance(step, NormalizeStep)), None
                )
                count = min(
                    panel.count,
                    panel.rows * panel.cols,
                    10 if source.source == "predictions" else 100,
                )
                line("    ax.set_axis_off()", origin)
                line(
                    f"    image_grid = grid[{index}].subgridspec({panel.rows}, {panel.cols})",
                    origin,
                )
                line(f"    sample_dataset = {role}_loader.dataset", source.origin)
                line(
                    f"    for sample_index in range(min({count}, len(sample_dataset))):",
                    source.origin,
                )
                line("        context.check_cancelled()", source.origin)
                line("        image, label = sample_dataset[sample_index]", source.origin)
                line("        display_image = image.detach().cpu().clone()", source.origin)
                if normalize:
                    line(
                        f"        display_image = display_image * torch.tensor({normalize.std!r}).view(-1, 1, 1) + torch.tensor({normalize.mean!r}).view(-1, 1, 1)",
                        source.origin,
                    )
                line("        display_image = display_image.clamp(0, 1)", source.origin)
                line("        sample_ax = fig.add_subplot(image_grid[sample_index])", origin)
                line("        if display_image.shape[0] == 1:", source.origin)
                line(
                    "            sample_ax.imshow(display_image.squeeze(0).numpy(), cmap='gray', vmin=0, vmax=1)",
                    source.origin,
                )
                line("        else:", source.origin)
                line(
                    "            sample_ax.imshow(display_image.permute(1, 2, 0).numpy())",
                    source.origin,
                )
                if source.source == "predictions":
                    line("        model.eval()", source.origin)
                    line("        with torch.no_grad():", source.origin)
                    line(
                        "            prediction = int(model(image.unsqueeze(0).to(device)).argmax(dim=1).item())",
                        source.origin,
                    )
                    line(
                        "        outcome = 'correct' if prediction == int(label) else 'incorrect'",
                        source.origin,
                    )
                    line(
                        "        sample_ax.set_title(f'Pred: {prediction}, true: {int(label)} ({outcome})')",
                        source.origin,
                    )
                else:
                    line("        sample_ax.set_title(f'True: {int(label)}')", source.origin)
                if panel.axis is None or not panel.axis.show_ticks:
                    line(
                        "        sample_ax.set_xticks([])",
                        panel.axis.origin if panel.axis else origin,
                    )
                    line(
                        "        sample_ax.set_yticks([])",
                        panel.axis.origin if panel.axis else origin,
                    )
            if panel.axis:
                contributors.append(panel.axis.origin.block_id)
                if not panel.axis.show_ticks:
                    line("    ax.set_xticks([])", panel.axis.origin)
                    line("    ax.set_yticks([])", panel.axis.origin)
            if panel.legend:
                contributors.append(panel.legend.block_id)
                if panel.chart_type != "image_grid":
                    line("    ax.legend()", panel.legend)
        logical = figure.save.relative_path if figure.save else None
        save_origin = figure.save.origin if figure.save else figure.origin
        if figure.save:
            contributors.append(figure.save.origin.block_id)
        line(
            f"    relative_path = context.figure_path({figure.id!r}, {phase!r}, {epoch}, {logical!r})",
            save_origin,
        )
        line("    with context.atomic_target(relative_path) as figure_path:", save_origin)
        line("        fig.savefig(figure_path, format='png', dpi=100)", save_origin)
        line(
            f"    context.artifact(relative_path, 'figure', {figure.origin.block_id!r}, {list(dict.fromkeys(contributors))!r}, {phase!r}, {epoch})",
            save_origin,
        )
        line("finally:", kind="scaffold")
        line("    plt.close(fig)", kind="scaffold")
