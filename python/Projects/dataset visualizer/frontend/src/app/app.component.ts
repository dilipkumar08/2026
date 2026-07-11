import { Component, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

const API = 'http://localhost:8000';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  constructor(private http: HttpClient) {}

  // --- Upload ---
  uploadStatus = signal('');
  columns = signal<string[]>([]);
  selectedFileName = signal('');

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    this.selectedFileName.set(file.name);
    const formData = new FormData();
    formData.append('file', file);

    this.uploadStatus.set('Uploading...');
    this.http.post<{ status?: string; rows?: number; columns?: string[]; error?: string }>(
      `${API}/upload`,
      formData
    ).subscribe({
      next: (res) => {
        if (res.error) {
          this.uploadStatus.set(res.error);
          return;
        }
        this.uploadStatus.set(`Loaded ${res.rows} rows.`);
        this.columns.set(res.columns ?? []);
        if (res.columns?.length) {
          this.xColumn.set(res.columns[0]);
          this.yColumn.set(res.columns[0]);
        }
      },
      error: (err) => this.uploadStatus.set(`Error: ${err.message}`),
    });
  }

  // --- Chart ---
  chartType = signal<'bar' | 'line'>('bar');
  xColumn = signal('');
  yColumn = signal('');
  agg = signal('sum');
  chartLabels = signal<string[]>([]);
  chartValues = signal<number[]>([]);
  chartError = signal('');

  // computed() derives a value FROM other signals — it recalculates
  // automatically whenever chartValues changes, no manual recompute needed.
  //
  // BUG FIX: the domain must always include 0, not just min/max of the
  // data. Aggregates like sum(profit) can be negative (this dataset has
  // loss-making rows), and the old maxValue-only scale — value/max*160 —
  // produced a negative bar height for negative values, which is an
  // invalid SVG <rect height> and either throws or silently fails to
  // render in most browsers. `create_chart` can also return `null` for a
  // NaN-derived aggregate (see server.py's _json_safe), so nulls are
  // coerced to 0 before computing the domain.
  private safeValues = computed(() => this.chartValues().map((v) => v ?? 0));
  private domainMin = computed(() => Math.min(...this.safeValues(), 0));
  private domainMax = computed(() => Math.max(...this.safeValues(), 0));
  private domainRange = computed(() => this.domainMax() - this.domainMin() || 1);

  generateChart(): void {
    this.chartError.set('');
    this.http.post<{ labels?: string[]; values?: number[]; error?: string }>(
      `${API}/chart`,
      { chart_type: this.chartType(), x_column: this.xColumn(), y_column: this.yColumn(), agg: this.agg() }
    ).subscribe({
      next: (res) => {
        if (res.error) {
          this.chartError.set(res.error);
          return;
        }
        this.chartLabels.set(res.labels ?? []);
        this.chartValues.set(res.values ?? []);
      },
      error: (err) => this.chartError.set(err.message),
    });
  }

  // Maps a value to a y-coordinate within the chart's 20-200 vertical band
  // (200 = bottom, 20 = top, matching the template's 600x220 viewBox), with
  // the zero line placed proportionally between domainMin and domainMax
  // rather than always pinned to the bottom. This is what lets negative
  // values draw *below* the zero line instead of producing a negative
  // height.
  private scaleY(value: number): number {
    return 200 - ((value - this.domainMin()) / this.domainRange()) * 180;
  }

  // y-coordinate of the zero baseline — bars start here, not always at 200.
  baselineY(): number {
    return this.scaleY(0);
  }

  // Whether the current chart's domain includes a negative value — used to
  // decide whether to draw the dashed zero-reference line in the template.
  hasNegativeValue(): boolean {
    return this.domainMin() < 0;
  }

  // Exact y-position for a data value (used by the line chart's dot
  // markers, which need the true point location -- unlike barY(), which
  // clamps to the baseline for negative bars).
  pointY(value: number): number {
    return this.scaleY(value ?? 0);
  }

  // Top-left y of the <rect> for this value (rects are drawn downward from
  // y, so for a negative value the "top" is actually the zero line).
  barY(value: number): number {
    const v = value ?? 0;
    return Math.min(this.scaleY(v), this.baselineY());
  }

  // Magnitude of the bar — always >= 0, safe to use as an SVG height.
  barHeight(value: number): number {
    const v = value ?? 0;
    return Math.abs(this.scaleY(v) - this.baselineY());
  }

  // Builds the "x,y x,y ..." point string for the SVG <polyline> line chart.
  // The +20 offset matches the left margin used by the bar x-positions and
  // by the line chart's <circle> dot markers in the template -- without it
  // the dots and the line they're meant to sit on drift 20px apart.
  linePoints(): string {
    const values = this.safeValues();
    const step = values.length > 1 ? 560 / (values.length - 1) : 0;
    return values
      .map((v, i) => `${i * step + 20},${this.scaleY(v)}`)
      .join(' ');
  }

  // --- Chat ---
  message = signal('');
  response = signal('');
  isLoading = signal(false);
  threadId = signal<string | null>(null);
  runId = signal<string | null>(null);
  feedbackSent = signal(false);

  send(): void {
    const text = this.message().trim();
    if (!text || this.isLoading()) return;

    this.isLoading.set(true);
    this.feedbackSent.set(false);

    this.http.post<{ response: string; thread_id: string; run_id: string }>(
      `${API}/chat`,
      { message: text, thread_id: this.threadId() }
    ).subscribe({
      next: (res) => {
        this.response.set(res.response);
        this.threadId.set(res.thread_id);
        this.runId.set(res.run_id);
        this.isLoading.set(false);
      },
      error: (err) => {
        this.response.set(`Error: ${err.message}`);
        this.isLoading.set(false);
      },
    });
  }

  sendFeedback(score: number): void {
    const runId = this.runId();
    if (!runId || this.feedbackSent()) return;
    this.http.post(`${API}/feedback`, { run_id: runId, score }).subscribe({
      next: () => this.feedbackSent.set(true),
    });
  }

  // --- Export ---
  exportStatus = signal('');

  exportSummary(): void {
    const summary = this.response().trim();
    if (!summary) return;

    this.exportStatus.set('Generating document...');
    this.http.post<{ download_url: string }>(`${API}/export`, {
      title: 'Analysis Summary',
      summary_text: summary,
    }).subscribe({
      next: (res) => {
        this.exportStatus.set('Ready.');
        window.open(`${API}${res.download_url}`, '_blank');
      },
      error: (err) => this.exportStatus.set(`Error: ${err.message}`),
    });
  }
}
