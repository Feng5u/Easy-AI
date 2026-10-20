import { useMemo, useState } from "react";
import type { CompileResult, ProjectDocument } from "../electron/bridge.js";
import { tutorials, tutorialTargets } from "./tutorials.js";
import type { TutorialId, TutorialTarget } from "./tutorials.js";
import { ConvolutionLab } from "./ConvolutionLab.js";
import { CodeView } from "./CodeView.js";
import "./TutorialPanel.css";

/** Deliberately small Markdown subset: text and headings; never HTML/links. */
export function LocalMarkdown({ text }: { text: string }) {
  return (
    <article>
      {text
        .trim()
        .split(/\n\s*\n/)
        .map((paragraph, index) =>
          paragraph.startsWith("# ") ? (
            <h3 key={index}>{paragraph.slice(2)}</h3>
          ) : paragraph.startsWith("## ") ? (
            <h4 key={index}>{paragraph.slice(3)}</h4>
          ) : (
            <p key={index}>{paragraph}</p>
          ),
        )}
    </article>
  );
}
export function TutorialPanel({
  topicId,
  onTopic,
  project,
  compilation,
  dirty,
  canCreateExample,
  onExample,
  onLocate,
}: {
  topicId: TutorialId;
  onTopic(topic: TutorialId): void;
  project: ProjectDocument | null;
  compilation: CompileResult | null;
  dirty: boolean;
  canCreateExample: boolean;
  onExample(): void;
  onLocate(target: TutorialTarget): void;
}) {
  const topic = tutorials.find((item) => item.id === topicId)!;
  return (
    <section
      className="panel tutorial-panel"
      aria-labelledby="tutorial-heading"
    >
      <h2 id="tutorial-heading" tabIndex={-1}>
        离线教程
      </h2>
      <p>本地内容，无需联网。这里只阅读和计算，不修改工程、不自动训练。</p>
      <nav aria-label="七个教学主题">
        {tutorials.map((item) => (
          <button
            type="button"
            key={item.id}
            aria-pressed={topicId === item.id}
            onClick={() => onTopic(item.id)}
          >
            {item.title}
          </button>
        ))}
      </nav>
      <Topic
        key={`${topicId}:${project?.projectId ?? "none"}`}
        topic={topic}
        project={project}
        compilation={compilation}
        dirty={dirty}
        onLocate={onLocate}
      />
      <p>
        示例副本将在你选择的新目录创建。未保存修改、保存中或任务进行时，请先处理当前工程；不会丢弃草稿，也不会覆盖已有工程或数据。
      </p>
      <button type="button" disabled={!canCreateExample} onClick={onExample}>
        在新目录创建 MNIST 教学副本
      </button>
    </section>
  );
}
function Topic({
  topic,
  project,
  compilation,
  dirty,
  onLocate,
}: {
  topic: (typeof tutorials)[number];
  project: ProjectDocument | null;
  compilation: CompileResult | null;
  dirty: boolean;
  onLocate(target: TutorialTarget): void;
}) {
  const targets = useMemo(
    () => (project ? tutorialTargets(project, topic.relevantBlockTypes) : []),
    [project, topic],
  );
  const [selection, setSelection] = useState("");
  const [showCode, setShowCode] = useState(false);
  const target = targets.find((item) => item.id === selection) ?? targets[0];
  const codeReady = Boolean(
    project &&
    !dirty &&
    target &&
    compilation?.revision === project.revision &&
    compilation.code &&
    compilation.sourceMap?.some(
      (span) =>
        span.origin.blockId === target.id &&
        span.origin.workspace === target.workspace,
    ),
  );
  return (
    <>
      <LocalMarkdown text={topic.markdown} />
      {topic.id === "convolution" && <ConvolutionLab />}
      {targets.length ? (
        <label className="field">
          关联本工程积木
          <select
            value={target.id}
            onChange={(event) => setSelection(event.target.value)}
          >
            {targets.map((item, index) => (
              <option key={item.id} value={item.id}>
                {item.label} #{index + 1}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <p>本工程尚无可关联的积木。可以先阅读或在新目录创建示例副本。</p>
      )}
      <div className="button-row">
        <button
          type="button"
          disabled={!target}
          onClick={() => target && onLocate(target)}
        >
          定位关联积木
        </button>
        <button
          type="button"
          disabled={!codeReady}
          onClick={() => {
            if (target && codeReady) {
              onLocate(target);
              setShowCode(true);
            }
          }}
        >
          显示对应代码
        </button>
      </div>
      {!codeReady && (
        <p>
          对应代码需先保存工程并“检查与编译”；缺失映射时不猜代码。教程计算仍可使用。
        </p>
      )}
      {showCode && codeReady && target && compilation?.code && (
        <section aria-label="教程关联的只读生成代码">
          <p>
            当前已保存 revision {project?.revision}；高亮来自 Python
            编译器映射，不修改代码。
          </p>
          <CodeView
            code={compilation.code}
            spans={compilation.sourceMap ?? []}
            selectedBlock={target.id}
            onSelectBlock={(id) => {
              const hit = targets.find((item) => item.id === id);
              if (hit) onLocate(hit);
            }}
          />
        </section>
      )}
    </>
  );
}
