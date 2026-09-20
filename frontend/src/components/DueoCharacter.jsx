import React from "react";

// Five bodies (flat blob shapes) and six faces, per the Dueo character system.
const BODIES = {
  cloud:
    "M169 100C169 113 167 128 165 138C162 148 158 155 153 161C147 167 142 172 133 175C124 178 111 180 100 180C89 180 76 178 67 175C58 172 53 167 47 161C42 155 38 148 35 138C33 128 31 113 31 100C31 87 33 72 35 62C38 52 42 45 47 39C53 33 58 28 67 25C76 22 89 20 100 20C111 20 124 22 133 25C142 28 147 33 153 39C158 45 162 52 165 62C167 72 169 87 169 100Z",
  bean:
    "M176 100C178 105 182 111 182 116C182 121 180 127 177 131C173 135 166 138 161 140C156 143 150 143 145 145C141 147 137 150 134 153C130 156 128 161 123 165C119 169 114 174 109 175C103 177 97 177 91 175C86 174 81 169 77 165C72 161 70 156 66 153C63 150 59 147 55 145C50 143 44 143 39 140C34 138 27 135 23 131C20 127 18 121 18 116C18 111 22 105 24 100C27 95 32 91 34 87C36 83 38 80 38 75C39 71 38 65 39 60C40 55 41 48 44 44C47 39 53 36 58 34C64 33 71 34 77 35C82 36 88 39 93 39C98 40 102 40 107 39C112 39 118 36 123 35C129 34 136 33 142 34C147 36 153 39 156 44C159 48 160 55 161 60C162 65 161 71 162 75C162 80 164 83 166 87C168 91 173 95 176 100Z",
  squircle:
    "M180 100C180 115 179 135 176 145C174 156 170 160 165 165C160 170 156 174 145 176C135 179 115 180 100 180C85 180 65 179 55 176C44 174 40 170 35 165C30 160 26 156 24 145C21 135 20 115 20 100C20 85 21 65 24 55C26 44 30 40 35 35C40 30 44 26 55 24C65 21 85 20 100 20C115 20 135 21 145 24C156 26 160 30 165 35C170 40 174 44 176 55C179 65 180 85 180 100Z",
  burst:
    "M166 100C172 103 184 110 184 113C183 117 170 119 163 120C156 122 143 118 142 121C140 124 150 132 153 139C156 145 163 158 160 160C158 163 145 156 139 153C132 150 124 140 121 142C118 143 122 156 120 163C119 170 117 183 113 184C110 184 103 172 100 166C97 160 96 147 93 146C89 146 85 158 80 163C74 168 64 177 61 176C58 174 60 160 61 153C62 146 69 136 67 133C64 131 54 138 47 139C40 140 26 142 24 139C23 136 32 126 37 120C42 115 54 111 54 107C53 104 40 103 34 100C28 97 16 90 16 87C17 83 30 81 37 80C44 78 57 82 58 79C60 76 50 68 47 61C44 55 37 42 40 40C42 37 55 44 61 47C68 50 76 60 79 58C82 57 78 44 80 37C81 30 83 17 87 16C90 16 97 28 100 34C103 40 104 53 107 54C111 54 115 42 120 37C126 32 136 23 139 24C142 26 140 40 139 47C138 54 131 64 133 67C136 69 146 62 153 61C160 60 174 58 176 61C177 64 168 74 163 80C158 85 146 89 146 93C147 96 160 97 166 100Z",
  flower:
    "M174 100C178 105 184 112 183 117C182 121 174 125 168 128C163 131 155 131 152 135C150 139 153 146 152 152C151 158 151 168 147 171C143 173 134 170 128 168C122 167 117 161 112 162C108 163 105 170 100 174C95 178 88 184 83 183C79 182 75 174 72 168C69 163 69 155 65 152C61 150 54 153 48 152C42 151 32 151 29 147C27 143 30 134 32 128C33 122 39 117 38 112C37 108 30 105 26 100C22 95 16 88 17 83C18 79 26 75 32 72C37 69 45 69 48 65C50 61 47 54 48 48C49 42 49 32 53 29C57 27 66 30 72 32C78 33 83 39 88 38C92 37 95 30 100 26C105 22 112 16 117 17C121 18 125 26 128 32C131 37 131 45 135 48C139 50 146 47 152 48C158 49 168 49 171 53C173 57 170 66 168 72C167 78 161 83 162 88C163 92 170 95 174 100Z",
};

const TONES = {
  lilac: "#A9A0F0",
  butter: "#F5D642",
  sky: "#8DBDF0",
  coral: "#FF9C7D",
  mint: "#7FD0A3",
};

const BLUSH = (
  <>
    <circle cx="62" cy="114" r="7" fill="#FF6B57" opacity=".35" />
    <circle cx="138" cy="114" r="7" fill="#FF6B57" opacity=".35" />
  </>
);

function Face({ mood }) {
  switch (mood) {
    case "focus":
      return (
        <>
          <path d="M70 100q8 8 16 0M114 100q8 8 16 0M92 122h16" fill="none" stroke="#16130F" strokeWidth="5" strokeLinecap="round" />
          {BLUSH}
        </>
      );
    case "sleepy":
      return (
        <>
          <path d="M70 104q8 5 16 0M114 104q8 5 16 0" fill="none" stroke="#16130F" strokeWidth="5" strokeLinecap="round" />
          <ellipse cx="100" cy="124" rx="6" ry="5" fill="#16130F" />
          {BLUSH}
        </>
      );
    case "alert":
      return (
        <>
          <g className="blink"><circle cx="80" cy="96" r="7" fill="#16130F" /></g>
          <g className="blink"><circle cx="120" cy="96" r="7" fill="#16130F" /></g>
          <ellipse cx="100" cy="124" rx="6" ry="8" fill="#16130F" />
        </>
      );
    case "cheer":
      return (
        <>
          <path d="M70 99q8-10 16 0M114 99q8-10 16 0M88 120q12 12 24 0" fill="none" stroke="#16130F" strokeWidth="5" strokeLinecap="round" />
          {BLUSH}
        </>
      );
    case "hmm":
      return (
        <>
          <g className="blink"><circle cx="80" cy="98" r="6.5" fill="#16130F" /></g>
          <g className="blink"><circle cx="120" cy="98" r="6.5" fill="#16130F" /></g>
          <path d="M86 122q7-7 14 0t14 0" fill="none" stroke="#16130F" strokeWidth="5" strokeLinecap="round" />
          <path d="M112 84q8-6 16-2" fill="none" stroke="#16130F" strokeWidth="4" strokeLinecap="round" />
        </>
      );
    case "happy":
    default:
      return (
        <>
          <g className="blink"><circle cx="80" cy="98" r="6.5" fill="#16130F" /><circle cx="82" cy="96" r="2" fill="#fff" /></g>
          <g className="blink"><circle cx="120" cy="98" r="6.5" fill="#16130F" /><circle cx="122" cy="96" r="2" fill="#fff" /></g>
          <path d="M90 121q10 9 20 0" fill="none" stroke="#16130F" strokeWidth="5" strokeLinecap="round" />
          {BLUSH}
        </>
      );
  }
}

export function DueoCharacter({ shape = "bean", mood = "happy", tone = "lilac", size = 160, bob = true, className = "", style = {} }) {
  const body = BODIES[shape] || BODIES.bean;
  const fill = TONES[tone] || TONES.lilac;
  return (
    <div className={`${bob ? "bob" : ""} ${className}`} style={{ width: size, height: size, ...style }}>
      <svg className="pop" viewBox="0 0 200 200" width={size} height={size} aria-hidden="true">
        <path fill={fill} d={body} />
        <ellipse cx="66" cy="52" rx="26" ry="13" fill="#fff" opacity=".28" transform="rotate(-24 66 52)" />
        <Face mood={mood} />
      </svg>
    </div>
  );
}

// Shield character — a blob holding a shield (used in the Shield section).
export function ShieldCharacter({ size = 190, className = "", style = {} }) {
  return (
    <div className={`bob ${className}`} style={{ width: size, height: size, ...style }}>
      <svg className="pop" viewBox="0 0 200 210" width={size} height={size} aria-hidden="true" style={{ overflow: "visible" }}>
        <ellipse cx="100" cy="206" rx="50" ry="5" fill="#16130F" opacity=".12" />
        <g transform="translate(10 4) scale(.9 .82)">
          <path fill="#A9A0F0" d="M180 100C180 115 179 135 176 145C174 156 170 160 165 165C160 170 156 174 145 176C135 179 115 180 100 180C85 180 65 179 55 176C44 174 40 170 35 165C30 160 26 156 24 145C21 135 20 115 20 100C20 85 21 65 24 55C26 44 30 40 35 35C40 30 44 26 55 24C65 21 85 20 100 20C115 20 135 21 145 24C156 26 160 30 165 35C170 40 174 44 176 55C179 65 180 85 180 100Z" />
        </g>
        <ellipse cx="66" cy="40" rx="24" ry="11" fill="#fff" opacity=".3" transform="rotate(-20 66 40)" />
        <g className="blink"><circle cx="78" cy="78" r="6.5" fill="#16130F" /></g>
        <g className="blink"><circle cx="122" cy="78" r="6.5" fill="#16130F" /></g>
        <path d="M89 97q11 9 22 0" fill="none" stroke="#16130F" strokeWidth="5" strokeLinecap="round" />
        <path d="M100 116L140 128V156Q140 184 100 200Q60 184 60 156V128Z" fill="#FFFFFF" />
        <path d="M100 116L140 128V156Q140 184 100 200Z" fill="#CBEBD8" />
        <path d="M100 116L140 128V156Q140 184 100 200Q60 184 60 156V128Z" fill="none" stroke="#16130F" strokeWidth="5" strokeLinejoin="round" />
        <path d="M83 156l12 12 23-26" fill="none" stroke="#16130F" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

export default DueoCharacter;
