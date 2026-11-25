import React from "react";
import { SAFETY_NOTICE } from "../../utils/constants";
import Icon from "../common/Icon";

export default function SafetyBanner() {
  return (
    <div className="safety-banner" role="note" aria-label="Academic prototype safety notice">
      <Icon name="shield" size={15} className="safety-banner-icon" />
      <span className="safety-banner-text">{SAFETY_NOTICE}</span>
    </div>
  );
}

