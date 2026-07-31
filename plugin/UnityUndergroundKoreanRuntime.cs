using System;
using System.Reflection;
using BepInEx;
using HarmonyLib;

namespace UnityUndergroundKoreanRuntime
{
    [BepInPlugin(
        "kr.ultima-underworld.korean.runtime",
        "Unity Underground Korean Runtime",
        "1.1.0")]
    [BepInDependency(
        "kr.ultima-underworld.korean",
        BepInDependency.DependencyFlags.HardDependency)]
    public sealed class RuntimePlugin : BaseUnityPlugin
    {
        private static MethodInfo translateMethod;

        [ThreadStatic]
        private static bool translatingFragment;

        private void Awake()
        {
            Type pluginType = AccessTools.TypeByName(
                "UnityUndergroundKorean.KoreanPlugin");
            if (pluginType == null)
            {
                Logger.LogError("기본 한국어 플러그인을 찾지 못했습니다.");
                return;
            }

            translateMethod = AccessTools.Method(
                pluginType, "Translate", new Type[] { typeof(string) });
            if (translateMethod == null)
            {
                Logger.LogError("기본 번역 메서드를 찾지 못했습니다.");
                return;
            }

            Harmony harmony = new Harmony(
                "kr.ultima-underworld.korean.runtime");
            harmony.Patch(
                translateMethod,
                postfix: new HarmonyMethod(
                    typeof(RuntimePlugin), nameof(TranslatePostfix)));
            Logger.LogInfo("v1.1.0 동적 문장 한국어 어순 보강이 활성화되었습니다.");
        }

        public static void TranslatePostfix(string __0, ref string __result)
        {
            if (translatingFragment || String.IsNullOrEmpty(__0))
                return;

            string translated = TranslateAssembled(__0);
            if (translated != null)
                __result = translated;
        }

        private static string TranslateAssembled(string source)
        {
            string fragment;

            if (TakePrefix(source, "It looks to be that of ", out fragment))
                return "그것은 " + TranslateFragment(fragment) + "의 것으로 보입니다.";
            if (TakePrefix(source, "They look to be those of ", out fragment))
                return "그것들은 " + TranslateFragment(fragment) + "의 것으로 보입니다.";

            if (TakePrefix(source, "You have advanced greatly in ", out fragment))
                return TranslateFragment(fragment) + " 기술이 크게 향상되었습니다.";
            if (TakePrefix(source, "You have advanced in ", out fragment))
                return TranslateFragment(fragment) + " 기술이 향상되었습니다.";
            if (TakePrefix(source, "You cannot advance in ", out fragment))
                return TranslateFragment(fragment) + " 기술은 향상시킬 수 없습니다.";
            if (TakePrefix(source, "You have attained experience level ", out fragment))
                return "경험 레벨 " + TranslateFragment(fragment) + "에 도달했습니다.";

            if (TakePrefix(source, "The Cup of Wonder is ", out fragment))
                return "경이의 잔은 " + TranslateFragment(fragment) + "에 있습니다.";
            if (TakePrefix(source, "You detect a creature ", out fragment))
                return "생명체 한 마리가 " + TranslateFragment(fragment) + "에서 감지됩니다.";
            if (TakePrefix(source, "You detect a few creatures ", out fragment))
                return "몇몇 생명체가 " + TranslateFragment(fragment) + "에서 감지됩니다.";
            if (TakePrefix(
                source, "You detect the activity of many creatures ", out fragment))
                return "많은 생명체의 움직임이 " +
                    TranslateFragment(fragment) + "에서 감지됩니다.";

            if (TakePrefix(source, "Your current vitality is ", out fragment))
                return "현재 생명력: " + TranslateFragment(fragment);
            if (TakePrefix(source, "Your current mana points are ", out fragment))
                return "현재 마나: " + TranslateFragment(fragment);
            if (TakePrefix(source, "Restoring Game ", out fragment))
                return "게임 불러오는 중: " + TranslateFragment(fragment);
            if (TakePrefix(source, "Saving Game ", out fragment))
                return "게임 저장 중: " + TranslateFragment(fragment);

            const string levelPrefix = "You are on the ";
            const string levelSuffix = " level of the Abyss.";
            if (source.StartsWith(levelPrefix, StringComparison.OrdinalIgnoreCase) &&
                source.EndsWith(levelSuffix, StringComparison.OrdinalIgnoreCase))
            {
                string value = source.Substring(
                    levelPrefix.Length,
                    source.Length - levelPrefix.Length - levelSuffix.Length);
                return "현재 스티지언 심연의 " + TranslateFragment(value) + "층에 있습니다.";
            }

            const string dayPrefix = "It is the ";
            const string daySuffix = " day of your imprisonment.";
            if (source.StartsWith(dayPrefix, StringComparison.OrdinalIgnoreCase) &&
                source.EndsWith(daySuffix, StringComparison.OrdinalIgnoreCase))
            {
                string value = source.Substring(
                    dayPrefix.Length,
                    source.Length - dayPrefix.Length - daySuffix.Length);
                return "감금된 지 " + TranslateFragment(value) + "일째입니다.";
            }

            if (TakePrefix(source, "You guess that it is currently ", out fragment))
                return "현재 시각은 " + TranslateFragment(fragment).TrimEnd('.') +
                    " 무렵으로 보입니다.";
            if (TakePrefix(source, "You are currently ", out fragment))
                return "현재 상태: " + TranslateFragment(fragment).TrimEnd('.') + ".";

            const string poisonPrefix = "You are ";
            const string poisonSuffix = " poisoned.";
            if (source.StartsWith(poisonPrefix, StringComparison.OrdinalIgnoreCase) &&
                source.EndsWith(poisonSuffix, StringComparison.OrdinalIgnoreCase))
            {
                string state = source.Substring(
                    poisonPrefix.Length,
                    source.Length - poisonPrefix.Length - poisonSuffix.Length);
                string translatedState = TranslateFragment(state);
                return translatedState.Length == 0
                    ? "중독되었습니다."
                    : translatedState + " 상태이며 중독되었습니다.";
            }

            if (TranslateObjectPrefix(
                source, "You destroyed the ", " 파괴했습니다.", out fragment))
                return fragment;
            if (TranslateObjectPrefix(
                source, "You damaged the ", " 손상시켰습니다.", out fragment))
                return fragment;
            if (TranslateObjectPrefix(
                source,
                "Your attempt has no effect on the ",
                "에는 아무런 효과가 없습니다.",
                out fragment))
                return "시도했지만 " + fragment;
            if (TranslateObjectPrefix(
                source,
                "You have partially repaired the ",
                " 일부 수리했습니다.",
                out fragment))
                return fragment;
            if (TranslateObjectPrefix(
                source,
                "You have fully repaired the ",
                " 완전히 수리했습니다.",
                out fragment))
                return fragment;

            if (TakePrefix(source, "You see ", out fragment))
            {
                string item = StripArticle(TranslateFragment(fragment)).TrimEnd('.');
                if (ContainsKorean(item))
                    return "당신은 " + item + ObjectParticle(item) + " 봅니다.";
            }

            string subject;
            if (TakeSuffix(source, " is currently active.", out subject))
                return SubjectSentence(subject, " 현재 활성화되어 있습니다.");
            if (TakeSuffix(source, " is nearly done", out subject))
                return SubjectSentence(subject, " 거의 다 되었습니다.");
            if (TakeSuffix(source, " is unstable", out subject))
                return SubjectSentence(subject, " 불안정합니다.");
            if (TakeSuffix(source, " is stable", out subject))
                return SubjectSentence(subject, " 안정적입니다.");
            if (TakeSuffix(source, " is angered by your action.", out subject))
                return SubjectSentence(subject, " 이 행동에 분노합니다.");
            if (TakeSuffix(source, " is annoyed by your action.", out subject))
                return SubjectSentence(subject, " 이 행동을 불쾌해합니다.");
            if (TakeSuffix(source, " notes your action.", out subject))
                return SubjectSentence(subject, " 이 행동을 눈여겨봅니다.");

            if (TakePrefix(
                source, "Your Rune of Warding has been set off ", out fragment))
                return "수호의 룬이 " + TranslateFragment(fragment) + "에서 발동했습니다.";

            string repair = TranslateRepairPrompt(source);
            if (repair != null)
                return repair;

            string ending = TranslateEndingSummary(source);
            if (ending != null)
                return ending;

            return null;
        }

        private static string TranslateRepairPrompt(string source)
        {
            const string prefix = "You think it will be ";
            const string middleText = " to repair the ";
            if (!source.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                return null;

            int middle = source.IndexOf(
                middleText, prefix.Length, StringComparison.OrdinalIgnoreCase);
            if (middle < 0)
                return null;

            string difficulty = TranslateFragment(source.Substring(
                prefix.Length, middle - prefix.Length));
            string item = source.Substring(middle + middleText.Length).Trim();
            bool asks = item.EndsWith(
                "Make an attempt?", StringComparison.OrdinalIgnoreCase);
            if (asks)
            {
                item = item.Substring(
                    0, item.Length - "Make an attempt?".Length).Trim();
            }

            item = StripArticle(TranslateFragment(item)).TrimEnd('.');
            if (!ContainsKorean(item))
                return null;

            string sentence = item + ObjectParticle(item) +
                " 수리하기는 " + difficulty + " 것으로 보입니다.";
            return asks ? sentence + " 시도하시겠습니까?" : sentence;
        }

        private static string TranslateEndingSummary(string source)
        {
            const string prefix = "A level ";
            const string middle = " after ";
            const string suffix = " days in the Abyss";
            if (!source.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) ||
                !source.EndsWith(suffix, StringComparison.OrdinalIgnoreCase))
                return null;

            int split = source.IndexOf(
                middle, prefix.Length, StringComparison.OrdinalIgnoreCase);
            if (split < 0)
                return null;

            string description = source.Substring(
                prefix.Length, split - prefix.Length).Trim();
            string days = source.Substring(
                split + middle.Length,
                source.Length - split - middle.Length - suffix.Length).Trim();
            return "심연에서 " + TranslateFragment(days) + "일을 보낸 " +
                TranslateFragment(description);
        }

        private static string SubjectSentence(string subject, string ending)
        {
            string translated = TranslateFragment(subject);
            return translated + SubjectParticle(translated) + ending;
        }

        private static bool TranslateObjectPrefix(
            string source, string prefix, string ending, out string result)
        {
            string remainder;
            if (!TakePrefix(source, prefix, out remainder))
            {
                result = null;
                return false;
            }

            string item = StripArticle(TranslateFragment(remainder)).TrimEnd('.');
            if (!ContainsKorean(item))
            {
                result = null;
                return false;
            }

            result = item + ObjectParticle(item) + ending;
            return true;
        }

        private static bool TakePrefix(
            string value, string prefix, out string remainder)
        {
            if (value.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            {
                remainder = value.Substring(prefix.Length).Trim();
                return remainder.Length > 0;
            }
            remainder = null;
            return false;
        }

        private static bool TakeSuffix(
            string value, string suffix, out string subject)
        {
            if (value.EndsWith(suffix, StringComparison.OrdinalIgnoreCase))
            {
                subject = value.Substring(0, value.Length - suffix.Length).Trim();
                return subject.Length > 0;
            }
            subject = null;
            return false;
        }

        private static string TranslateFragment(string value)
        {
            if (String.IsNullOrEmpty(value) || translateMethod == null)
                return value == null ? String.Empty : value.Trim();

            string trimmed = value.Trim();
            try
            {
                translatingFragment = true;
                object translated = translateMethod.Invoke(
                    null, new object[] { trimmed });
                return translated as string ?? trimmed;
            }
            catch
            {
                return trimmed;
            }
            finally
            {
                translatingFragment = false;
            }
        }

        private static string StripArticle(string value)
        {
            if (String.IsNullOrEmpty(value))
                return value;
            if (value.StartsWith("the ", StringComparison.OrdinalIgnoreCase))
                return value.Substring(4).TrimStart();
            if (value.StartsWith("an ", StringComparison.OrdinalIgnoreCase))
                return value.Substring(3).TrimStart();
            if (value.StartsWith("a ", StringComparison.OrdinalIgnoreCase))
                return value.Substring(2).TrimStart();
            return value;
        }

        private static bool ContainsKorean(string value)
        {
            if (String.IsNullOrEmpty(value))
                return false;
            foreach (char character in value)
            {
                if ((character >= '\uac00' && character <= '\ud7a3') ||
                    (character >= '\u3131' && character <= '\u318e'))
                    return true;
            }
            return false;
        }

        private static string SubjectParticle(string value)
        {
            return HasFinalConsonant(value) ? "이" : "가";
        }

        private static string ObjectParticle(string value)
        {
            return HasFinalConsonant(value) ? "을" : "를";
        }

        private static bool HasFinalConsonant(string value)
        {
            if (String.IsNullOrEmpty(value))
                return false;
            for (int index = value.Length - 1; index >= 0; index--)
            {
                char character = value[index];
                if (character >= '\uac00' && character <= '\ud7a3')
                    return ((character - '\uac00') % 28) != 0;
                if (Char.IsLetterOrDigit(character))
                    return false;
            }
            return false;
        }
    }
}
