import React from "react";

export function Skeleton({ w = "100%", h = 20, r = 20, style = {} }) {
  return <div className="skel" style={{ width: w, height: h, borderRadius: r, ...style }} data-testid="skeleton" />;
}

export default Skeleton;
