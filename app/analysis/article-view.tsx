import Link from 'next/link';
import type { ReactNode } from 'react';
import { findPublished, isAutomated, isPublished, tokens, type Article } from '../lib/articles';
import { getTeamById, teamLabel } from '../team-data';
import { centralDateTime } from '../lib/format';

function Rich({ text }: { text: string }) {
  return (
    <>
      {tokens(text).map((part, index) => {
        if ('text' in part) return <span key={index}>{part.text}</span>;
        if ('team' in part) {
          const team = getTeamById(part.team);
          return team ? <Link key={index} href={`/team/${team.slug}`}>{team.team}</Link> : <span key={index}>{teamLabel(part.team)}</span>;
        }
        const target = findPublished(part.article);
        return target ? <Link key={index} href={`/analysis/${target.slug}`}>{target.title}</Link> : <span key={index}>risers-and-fallers analysis</span>;
      })}
    </>
  );
}

/** Renders an article; `between` is placed after the given section index (ads, if eligible). */
export function ArticleView({ article, between }: { article: Article; between?: Record<number, ReactNode> }) {
  const published = isPublished(article);
  const automated = isAutomated(article);
  return (
    <article className="mf-doc mf-article">
      <p className="eyebrow">Weekly Analysis · {article.season} Week {article.week}</p>
      <h1>{article.title}</h1>
      <p className="advertise-intro">{article.dek}</p>
      <p className="mf-doc-meta">
        {published && automated ? (
          <>Published {centralDateTime(article.published_at!)}
            {article.updated_at ? <> · Updated {centralDateTime(article.updated_at)} for a corrected snapshot</> : null}
            {' '}· <strong>Automated analysis</strong> generated from verified data; publication approved by {article.approved_by}; not individually reviewed · </>
        ) : published ? (
          <>Published {centralDateTime(article.published_at!)} · Reviewed by {article.reviewed_by} · </>
        ) : (
          <><strong>Draft — not reviewed, not public.</strong> Generated from data; requires human review before publication. · </>
        )}
        Data: Week {article.week} snapshot generated {centralDateTime(article.snapshot_generated_at)}, formula {article.formula_version}
      </p>
      {article.sections.map((section, index) => (
        <section key={section.heading}>
          <h2>{section.heading}</h2>
          {section.paragraphs?.map((paragraph, p) => <p key={p}><Rich text={paragraph} /></p>)}
          {section.table && (
            <div className="table-scroll" role="region" aria-label={section.heading} tabIndex={0}>
              <table className="mf-weights-table">
                <thead><tr>{section.table.columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead>
                <tbody>
                  {section.table.rows.map((row, r) => (
                    <tr key={r}>{row.map((cell, c) => <td key={c} className={c > 0 ? 'tabular' : undefined}><Rich text={cell} /></td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {between?.[index]}
        </section>
      ))}
      <h2>Sources</h2>
      <ul>
        {article.sources.map((source) => (
          <li key={source.url}>
            {source.url.startsWith('/') ? <Link href={source.url}>{source.label}</Link> : <a href={source.url} rel="noopener">{source.label}</a>}
          </li>
        ))}
      </ul>
      {article.limitations.length > 0 && (
        <>
          <h2>Limitations</h2>
          <ul>{article.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
        </>
      )}
      <p className="mf-doc-meta">
        {automated
          ? 'Written automatically from verified MFPI data each week. It describes results and ratings only; it does not include opinions, quotes or game narratives.'
          : 'Written from verified MFPI data and reviewed by the named editor before publication.'}{' '}
        Spot an error? <Link href="/corrections">Report a correction</Link>.
      </p>
    </article>
  );
}
