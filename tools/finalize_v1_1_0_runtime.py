#!/usr/bin/env python3
"""Finalize the v1.1.0 translation map and runtime composite sentence handling."""
from pathlib import Path


def refine_application_tool() -> None:
    path = Path("tools/apply_completed_retranslations.py")
    text = path.read_text(encoding="utf-8")
    old = '''    return (\n        source in DYNAMIC_SOURCES\n        or "%s" in source\n        or "{0}" in source\n        or source != source.strip()\n    )\n'''
    new = '''    return (\n        source in DYNAMIC_SOURCES\n        or "%s" in source\n        or "{0}" in source\n    )\n'''
    if old in text:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
    elif new not in text:
        raise RuntimeError("dynamic source rule not found")


def refine_plugin() -> None:
    path = Path("plugin/UnityUndergroundKorean.cs")
    code = path.read_text(encoding="utf-8")
    code = code.replace(
        '[BepInPlugin("kr.ultima-underworld.korean", "Unity Underground Korean", "1.0.1")]',
        '[BepInPlugin("kr.ultima-underworld.korean", "Unity Underground Korean", "1.1.0")]',
        1,
    )

    call = (
        "            string assembled = TranslateAssembledGameText(result);\n"
        "            if (assembled != result)\n"
        "                return assembled;\n\n"
    )
    anchor = "            string result = source;\n\n"
    if "TranslateAssembledGameText(result)" not in code:
        if anchor not in code:
            raise RuntimeError("TranslateCompositeText insertion anchor not found")
        code = code.replace(anchor, anchor + call, 1)

    helper = r'''
        private static string TranslateAssembledGameText(string value)
        {
            if (String.IsNullOrEmpty(value))
                return value;

            string fragment;
            if (TryTakePrefix(value, "It looks to be that of ", out fragment))
                return "그것은 " + TranslateKnownFragment(fragment) + "의 것으로 보입니다.";
            if (TryTakePrefix(value, "They look to be those of ", out fragment))
                return "그것들은 " + TranslateKnownFragment(fragment) + "의 것으로 보입니다.";
            if (TryTakePrefix(value, "You have advanced greatly in ", out fragment))
                return TranslateKnownFragment(fragment) + " 기술이 크게 향상되었습니다.";
            if (TryTakePrefix(value, "You have advanced in ", out fragment))
                return TranslateKnownFragment(fragment) + " 기술이 향상되었습니다.";
            if (TryTakePrefix(value, "You cannot advance in ", out fragment))
                return TranslateKnownFragment(fragment) + " 기술은 향상시킬 수 없습니다.";
            if (TryTakePrefix(value, "The Cup of Wonder is ", out fragment))
                return "경이의 잔은 " + TranslateKnownFragment(fragment) + "에 있습니다.";
            if (TryTakePrefix(value, "You detect a creature ", out fragment))
                return "생명체 한 마리가 " + TranslateKnownFragment(fragment) + "에서 감지됩니다.";
            if (TryTakePrefix(value, "You detect a few creatures ", out fragment))
                return "몇몇 생명체가 " + TranslateKnownFragment(fragment) + "에서 감지됩니다.";
            if (TryTakePrefix(value, "You detect the activity of many creatures ", out fragment))
                return "많은 생명체의 움직임이 " + TranslateKnownFragment(fragment) + "에서 감지됩니다.";
            if (TryTakePrefix(value, "Your current vitality is ", out fragment))
                return "현재 생명력: " + TranslateKnownFragment(fragment);
            if (TryTakePrefix(value, "Your current mana points are ", out fragment))
                return "현재 마나: " + TranslateKnownFragment(fragment);
            if (TryTakePrefix(value, "You have attained experience level ", out fragment))
                return "경험 레벨 " + TranslateKnownFragment(fragment) + "에 도달했습니다.";
            if (TryTakePrefix(value, "Restoring Game ", out fragment))
                return "게임 불러오는 중: " + TranslateKnownFragment(fragment);
            if (TryTakePrefix(value, "Saving Game ", out fragment))
                return "게임 저장 중: " + TranslateKnownFragment(fragment);

            if (TryTranslateObjectPrefix(value, "You destroyed the ", " 파괴했습니다.", out fragment))
                return fragment;
            if (TryTranslateObjectPrefix(value, "You damaged the ", " 손상시켰습니다.", out fragment))
                return fragment;
            if (TryTranslateObjectPrefix(value, "Your attempt has no effect on the ", "에는 아무런 효과가 없습니다.", out fragment))
                return "시도했지만 " + fragment;
            if (TryTranslateObjectPrefix(value, "You have partially repaired the ", " 일부 수리했습니다.", out fragment))
                return fragment;
            if (TryTranslateObjectPrefix(value, "You have fully repaired the ", " 완전히 수리했습니다.", out fragment))
                return fragment;

            if (TryTakePrefix(value, "You see ", out fragment))
            {
                string objectName = StripLeadingEnglishArticle(TranslateKnownFragment(fragment)).TrimEnd('.');
                if (ContainsKorean(objectName))
                    return "당신은 " + objectName + GetObjectParticle(objectName) + " 봅니다.";
            }

            string subject;
            if (TryTakeSuffix(value, " is currently active.", out subject))
                return BuildSubjectSentence(subject, " 현재 활성화되어 있습니다.");
            if (TryTakeSuffix(value, " poisoned.", out subject))
                return BuildSubjectSentence(subject, " 중독되었습니다.");
            if (TryTakeSuffix(value, " is nearly done", out subject))
                return BuildSubjectSentence(subject, " 거의 다 되었습니다.");
            if (TryTakeSuffix(value, " is unstable", out subject))
                return BuildSubjectSentence(subject, " 불안정합니다.");
            if (TryTakeSuffix(value, " is stable", out subject))
                return BuildSubjectSentence(subject, " 안정적입니다.");
            if (TryTakeSuffix(value, " is angered by your action.", out subject))
                return BuildSubjectSentence(subject, " 이 행동에 분노합니다.");
            if (TryTakeSuffix(value, " is annoyed by your action.", out subject))
                return BuildSubjectSentence(subject, " 이 행동을 불쾌해합니다.");
            if (TryTakeSuffix(value, " notes your action.", out subject))
                return BuildSubjectSentence(subject, " 이 행동을 눈여겨봅니다.");

            const string repairPrefix = "You think it will be ";
            const string repairMiddle = " to repair the ";
            if (value.StartsWith(repairPrefix, StringComparison.OrdinalIgnoreCase))
            {
                int middle = value.IndexOf(repairMiddle, repairPrefix.Length, StringComparison.OrdinalIgnoreCase);
                if (middle >= 0)
                {
                    string difficulty = TranslateKnownFragment(value.Substring(
                        repairPrefix.Length, middle - repairPrefix.Length));
                    string item = value.Substring(middle + repairMiddle.Length).Trim();
                    bool asks = item.EndsWith("Make an attempt?", StringComparison.OrdinalIgnoreCase);
                    if (asks)
                        item = item.Substring(0, item.Length - "Make an attempt?".Length).Trim();
                    item = StripLeadingEnglishArticle(TranslateKnownFragment(item)).TrimEnd('.');
                    if (ContainsKorean(item))
                    {
                        string sentence = item + GetObjectParticle(item) + " 수리하기는 " + difficulty + " 것으로 보입니다.";
                        return asks ? sentence + " 시도하시겠습니까?" : sentence;
                    }
                }
            }

            return value;
        }

        private static string BuildSubjectSentence(string subject, string ending)
        {
            string translated = TranslateKnownFragment(subject);
            return translated + GetSubjectParticle(translated) + ending;
        }

        private static bool TryTakePrefix(string value, string prefix, out string remainder)
        {
            if (value.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            {
                remainder = value.Substring(prefix.Length).Trim();
                return remainder.Length > 0;
            }
            remainder = null;
            return false;
        }

        private static bool TryTakeSuffix(string value, string suffix, out string subject)
        {
            if (value.EndsWith(suffix, StringComparison.OrdinalIgnoreCase))
            {
                subject = value.Substring(0, value.Length - suffix.Length).Trim();
                return subject.Length > 0;
            }
            subject = null;
            return false;
        }

        private static bool TryTranslateObjectPrefix(
            string value, string prefix, string koreanEnding, out string translated)
        {
            string remainder;
            if (!TryTakePrefix(value, prefix, out remainder))
            {
                translated = null;
                return false;
            }
            string item = StripLeadingEnglishArticle(TranslateKnownFragment(remainder)).TrimEnd('.');
            if (!ContainsKorean(item))
            {
                translated = null;
                return false;
            }
            translated = item + GetObjectParticle(item) + koreanEnding;
            return true;
        }

        private static string TranslateKnownFragment(string value)
        {
            if (String.IsNullOrEmpty(value))
                return value;
            string trimmed = value.Trim();
            string translated;
            if (Exact.TryGetValue(trimmed, out translated))
                return translated.Trim();
            string normalized = Normalize(trimmed);
            if (Normalized.TryGetValue(normalized, out translated))
                return translated.Trim();
            if (ShortUiTerms.TryGetValue(normalized, out translated))
                return translated.Trim();
            return trimmed;
        }

'''
    helper_anchor = "        private static string RemoveEnglishArticlesBeforeKorean(string value)\n"
    if "private static string TranslateAssembledGameText" not in code:
        if helper_anchor not in code:
            raise RuntimeError("helper insertion anchor not found")
        code = code.replace(helper_anchor, helper + helper_anchor, 1)

    path.write_text(code, encoding="utf-8")


def main() -> None:
    refine_application_tool()
    refine_plugin()
    print("v1.1.0 runtime source finalization complete")


if __name__ == "__main__":
    main()
