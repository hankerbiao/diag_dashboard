import { useState, useEffect, useCallback } from 'react';

interface UseTypingAnimationOptions {
  texts: string[];
  typeSpeed?: number;
  deleteSpeed?: number;
  pauseDuration?: number;
}

/**
 * 打字机动画 hook
 * @param texts - 循环显示的文本数组
 * @param typeSpeed - 打字速度（毫秒/字符）
 * @param deleteSpeed - 删除速度（毫秒/字符）
 * @param pauseDuration - 打字完成后停顿时间
 */
export function useTypingAnimation({
  texts,
  typeSpeed = 50,
  deleteSpeed = 20,
  pauseDuration = 1800,
}: UseTypingAnimationOptions) {
  const [index, setIndex] = useState(0);
  const [displayText, setDisplayText] = useState('');
  const [isTyping, setIsTyping] = useState(true);

  useEffect(() => {
    const current = texts[index];

    let timer: ReturnType<typeof setTimeout>;

    if (isTyping) {
      if (displayText.length < current.length) {
        timer = setTimeout(() => {
          setDisplayText(current.slice(0, displayText.length + 1));
        }, typeSpeed);
      } else {
        timer = setTimeout(() => {
          setIsTyping(false);
        }, pauseDuration);
      }
    } else {
      if (displayText.length > 0) {
        timer = setTimeout(() => {
          setDisplayText(displayText.slice(0, -1));
        }, deleteSpeed);
      } else {
        timer = setTimeout(() => {
          setIndex((prev) => (prev + 1) % texts.length);
          setIsTyping(true);
        }, 350);
      }
    }

    return () => clearTimeout(timer);
  }, [displayText, isTyping, index, texts, typeSpeed, deleteSpeed, pauseDuration]);

  return { displayText, isTyping };
}