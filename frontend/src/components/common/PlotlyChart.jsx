import { useEffect, useRef } from 'react';

const PLOTLY_CONFIG = {
  responsive: true,
  displayModeBar: 'hover',
  displaylogo: false,
  modeBarButtonsToRemove: [
    'lasso2d', 'select2d', 'zoomIn2d', 'zoomOut2d',
    'autoScale2d', 'pan2d', 'toggleSpikelines',
    'hoverClosestCartesian', 'hoverCompareCartesian',
  ],
};

/** Wrapper around Plotly.js matching the original chart layout and hover styling */
export function PlotlyChart({ data, layout, style }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || !window.Plotly) return;
    const defaultLayout = {
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif', size: 12, color: '#64748B' },
      margin: { l: 44, r: 16, t: 16, b: 36 },
      hoverlabel: {
        bgcolor: '#FFFFFF',
        bordercolor: 'rgba(15, 23, 42, 0.16)',
        font: { family: 'Inter, sans-serif', size: 12, color: '#0F172A' },
        align: 'left',
      },
      xaxis: {
        showgrid: false,
        zeroline: false,
        linecolor: 'rgba(15, 23, 42, 0.08)',
        tickfont: { size: 11, color: '#64748B' },
        automargin: true,
      },
      yaxis: {
        showgrid: true,
        gridcolor: '#EDF2F7',
        gridwidth: 1,
        zeroline: false,
        tickfont: { size: 11, color: '#64748B' },
        automargin: true,
      },
      ...layout,
    };

    window.Plotly.react(el, data, defaultLayout, PLOTLY_CONFIG);

    return () => {
      if (window.Plotly && el) {
        window.Plotly.purge(el);
      }
    };
  }, [data, layout]);

  return <div ref={ref} style={{ width: '100%', height: '100%', ...style }} />;
}
