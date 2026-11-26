import React from 'react';
import PropTypes from 'prop-types';
import { HeartHandshake, Mountain, PawPrint, Sofa } from 'lucide-react';
import { Badge } from './ui';
import { petTypes } from '../data/matchGameQuestions';

// 毛孩類型卡片：配對小遊戲結果頁（T10）與個人中心配對檔案分頁（T09）共用
const TYPE_ICONS = {
  'outdoor-buddy': Mountain,
  'balanced-buddy': HeartHandshake,
  'couch-buddy': Sofa,
};

/**
 * 依 petType.code 對應 matchGameQuestions.js 的 petTypes 取名稱與說明；
 * 對應不到時（例如題目改版後的舊資料）改用傳入的 label、description，圖示用腳印。
 * children 放在卡片下方，例如按鈕。
 */
const PetTypeCard = ({ petType, children, className = '' }) => {
  const known = petTypes.find((t) => t.code === petType.code);
  const { label, description } = known || petType;
  const Icon = TYPE_ICONS[petType.code] || PawPrint;

  return (
    <div className={`flex flex-col items-center text-center ${className}`}>
      <div className="w-20 h-20 rounded-full bg-orange-100 flex items-center justify-center mb-4">
        <Icon className="w-10 h-10 text-orange-500" aria-hidden="true" />
      </div>
      <Badge variant="primary">你的毛孩類型</Badge>
      <h2 className="mt-3 text-2xl font-bold text-gray-900">{label}</h2>
      {description && <p className="mt-2 max-w-md text-gray-600">{description}</p>}
      {children}
    </div>
  );
};

PetTypeCard.propTypes = {
  petType: PropTypes.shape({
    code: PropTypes.string,
    label: PropTypes.string.isRequired,
    description: PropTypes.string,
  }).isRequired,
  children: PropTypes.node,
  className: PropTypes.string,
};

export default PetTypeCard;
