"use client";

// Plotly is browser-only and heavy, so it's wrapped here and loaded via a
// client-only dynamic import (see Plot.jsx). Using the dist-min build keeps the
// bundle smaller than the full plotly.js default.
import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-dist-min";

const Plot = createPlotlyComponent(Plotly);
export default Plot;
