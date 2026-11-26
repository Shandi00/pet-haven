import React from 'react';
import PropTypes from 'prop-types';
import { AlertTriangle, Check, Sparkles, ThumbsDown, ThumbsUp } from 'lucide-react';
import { Badge, Button, Card } from './ui';
import { getPetPhotoUrl } from '../utils/imageHelpers';

// Top 3 推薦卡片（T15）：item 是契約 §2 的一筆 items[]
const SPECIES = { dog: '狗', cat: '貓' };
const SIZE = { small: '小型', medium: '中型', large: '大型', 'extra-large': '特大型' };
const ACTIVITY = { low: '低', moderate: '中', high: '高' };
const LEVEL = {
  perfect: { label: '非常適合', variant: 'success' },
  excellent: { label: '很適合', variant: 'success' },
  good: { label: '適合', variant: 'primary' },
  fair: { label: '尚可', variant: 'warning' },
  poor: { label: '較不適合', variant: 'default' },
};

const ageText = (age) => (age?.value ? `${age.value} ${age.unit === 'months' ? '個月' : '歲'}` : '');

const Top3Card = ({ item, rank, onLike, onDislike, disabled = false }) => {
  const { pet, score, matchLevel, reason } = item;
  const level = LEVEL[matchLevel] || LEVEL.good;
  const facts = [SPECIES[pet.species], pet.breed, ageText(pet.age), SIZE[pet.size],
    pet.activityLevel && `活動量${ACTIVITY[pet.activityLevel] || pet.activityLevel}`].filter(Boolean);

  return (
    <Card className="flex flex-col h-full overflow-hidden" padding="none">
      <div className="relative">
        <img
          src={pet.photo || getPetPhotoUrl(null)}
          alt={pet.name}
          className="w-full h-48 object-cover bg-gray-100"
          onError={(e) => {
            // 只換一次替代圖，避免替代圖也載入失敗時一直觸發 onError
            if (e.currentTarget.dataset.fallback) return;
            e.currentTarget.dataset.fallback = '1';
            e.currentTarget.src = getPetPhotoUrl(null);
          }}
        />
        {rank && (
          <span className="absolute top-3 left-3 bg-white/90 text-gray-900 text-sm font-bold rounded-full w-8 h-8 flex items-center justify-center">
            {rank}
          </span>
        )}
      </div>

      <div className="flex flex-col flex-1 p-5 gap-4">
        <div>
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-xl font-bold text-gray-900">{pet.name}</h3>
            <div className="text-right shrink-0">
              <div className="text-2xl font-bold text-primary-600">{score}<span className="text-sm font-medium"> 分</span></div>
              <Badge variant={level.variant} size="sm">{level.label}</Badge>
            </div>
          </div>
          <p className="mt-1 text-sm text-gray-600">{facts.join('・')}</p>
        </div>

        <div className="space-y-2">
          <p className="text-gray-800">{reason.summary}</p>
          {reason.source === 'ai' ? (
            <p className="flex items-center gap-1 text-xs text-primary-600">
              <Sparkles className="w-3.5 h-3.5" aria-hidden="true" />
              AI 依你的配對檔案與動物資料產生
            </p>
          ) : (
            <p className="text-xs text-gray-500">目前使用規則推薦（這次沒有用到 AI）</p>
          )}
        </div>

        {reason.highlights?.length > 0 && (
          <ul className="space-y-1" aria-label="推薦原因">
            {reason.highlights.map((h) => (
              <li key={h} className="flex items-start gap-2 text-sm text-gray-700">
                <Check className="w-4 h-4 mt-0.5 text-green-600 shrink-0" aria-hidden="true" />
                {h}
              </li>
            ))}
          </ul>
        )}

        {reason.cautions?.length > 0 && (
          <div className="rounded-lg bg-yellow-50 p-3">
            <p className="text-sm font-medium text-yellow-800">注意事項</p>
            <ul className="mt-1 space-y-1">
              {reason.cautions.map((c) => (
                <li key={c} className="flex items-start gap-2 text-sm text-yellow-800">
                  <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
                  {c}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-auto grid grid-cols-2 gap-3 pt-2">
          <Button
            variant="outline"
            onClick={() => onDislike(pet)}
            disabled={disabled}
            aria-label={`${pet.name} 不適合`}
            className="inline-flex items-center justify-center gap-1"
          >
            <ThumbsDown className="w-4 h-4" aria-hidden="true" />
            不適合
          </Button>
          <Button
            onClick={() => onLike(pet)}
            disabled={disabled}
            aria-label={`${pet.name} 適合`}
            className="inline-flex items-center justify-center gap-1"
          >
            <ThumbsUp className="w-4 h-4" aria-hidden="true" />
            適合
          </Button>
        </div>
      </div>
    </Card>
  );
};

Top3Card.propTypes = {
  item: PropTypes.shape({
    pet: PropTypes.shape({
      _id: PropTypes.string.isRequired,
      name: PropTypes.string.isRequired,
      species: PropTypes.string,
      breed: PropTypes.string,
      age: PropTypes.shape({ value: PropTypes.number, unit: PropTypes.string }),
      size: PropTypes.string,
      activityLevel: PropTypes.string,
      photo: PropTypes.string,
    }).isRequired,
    score: PropTypes.number.isRequired,
    matchLevel: PropTypes.string,
    reason: PropTypes.shape({
      summary: PropTypes.string.isRequired,
      highlights: PropTypes.arrayOf(PropTypes.string),
      cautions: PropTypes.arrayOf(PropTypes.string),
      source: PropTypes.oneOf(['ai', 'rule']).isRequired,
    }).isRequired,
  }).isRequired,
  rank: PropTypes.number,
  onLike: PropTypes.func.isRequired,
  onDislike: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};

export default Top3Card;
