using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using Newtonsoft.Json.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace UnityUndergroundKorean
{
    [BepInPlugin("kr.ultima-underworld.korean", "Unity Underground Korean", "1.0.1")]
    public sealed class KoreanPlugin : BaseUnityPlugin
    {
        private static ManualLogSource Log;
        private static readonly Dictionary<string, string> Exact =
            new Dictionary<string, string>(StringComparer.Ordinal);
        private static readonly Dictionary<string, string> Normalized =
            new Dictionary<string, string>(StringComparer.Ordinal);
        private static readonly Dictionary<string, string> ShortUiTerms =
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                { "Fighter", "전사" }, { "Mage", "마법사" }, { "Bard", "음유시인" },
                { "Tinker", "땜장이" }, { "Druid", "드루이드" }, { "Paladin", "성기사" },
                { "Ranger", "레인저" }, { "Shepherd", "목동" },
                { "Attack", "공격" }, { "Defense", "방어" }, { "Unarmed", "맨손" },
                { "Sword", "검술" }, { "Axe", "도끼술" }, { "Mace", "둔기술" },
                { "Missile", "원거리" }, { "Mana", "마나" }, { "Lore", "지식" },
                { "Casting", "주문 시전" }, { "Traps", "함정" }, { "Search", "수색" },
                { "Track", "추적" }, { "Sneak", "은신" }, { "Repair", "수리" },
                { "Charm", "매혹" }, { "Picklock", "자물쇠 따기" }, { "Acrobat", "곡예" },
                { "Appraise", "감정" }, { "Swimming", "수영" },
                { "Back", "뒤로" }, { "Cancel", "취소" }, { "Clear", "지우기" },
                { "Close", "닫기" }, { "Open", "열기" }, { "Select", "선택" },
                { "Use", "사용" }, { "Take", "줍기" }, { "Look", "살펴보기" },
                { "Talk", "대화" }, { "Drop", "내려놓기" }, { "Pick up", "줍기" },
                { "Inventory", "소지품" }, { "Map", "지도" }, { "Magic", "마법" },
                { "Cast", "시전" }, { "Read", "읽기" }, { "Eat", "먹기" },
                { "Drink", "마시기" }, { "Equip", "장착" }
            };
        private static readonly HashSet<int> FontsWithFallback = new HashSet<int>();

        private static Font defaultUiFont;
        private static Font characterFont;
        private static TMP_FontAsset koreanTmpFont;
        private static bool loggedTmpFontFailure;
        private float nextScan;
        private float nextFontAttempt;

        private void Awake()
        {
            Log = Logger;
            LoadTranslations();
            InstallPatches();
            ScanVisibleText();
            Logger.LogInfo("Unity Underground Korean patch is active (" + Exact.Count + " entries).");
        }

        private void Start()
        {
            CreateKoreanFonts();
            ScanVisibleText();
        }

        private void Update()
        {
            if (koreanTmpFont == null && Time.unscaledTime >= nextFontAttempt)
            {
                nextFontAttempt = Time.unscaledTime + 2f;
                TryCreateTmpFont();
            }

            if (Time.unscaledTime < nextScan)
                return;

            nextScan = Time.unscaledTime + 0.25f;
            ScanVisibleText();
        }

        private static void LoadTranslations()
        {
            string path = Path.Combine(Paths.GameRootPath, "translations", "global_text_map.json");
            if (!File.Exists(path))
            {
                Log.LogError("Translation file was not found: " + path);
                return;
            }

            JObject root = JObject.Parse(File.ReadAllText(path));
            foreach (JProperty block in root.Properties())
            {
                JObject entries = block.Value as JObject;
                if (entries == null)
                    continue;

                foreach (JProperty entry in entries.Properties())
                {
                    string source = entry.Name;
                    string translated = entry.Value.Type == JTokenType.String
                        ? (string)entry.Value
                        : entry.Value.ToString();

                    if (String.IsNullOrEmpty(source) || String.IsNullOrEmpty(translated) || source == translated)
                        continue;

                    Exact[source] = translated;
                    string normalized = Normalize(source);
                    if (!Normalized.ContainsKey(normalized))
                        Normalized[normalized] = translated;
                }
            }
        }

        private static string Normalize(string value)
        {
            return value == null
                ? null
                : value.Replace("\r\n", "\n")
                    .Replace("\u00ad", "")
                    .Replace("’", "'")
                    .Replace("—", " - ")
                    .Trim();
        }

        public static string Translate(string source)
        {
            if (String.IsNullOrEmpty(source) || Exact.Count == 0)
                return source;

            string translated;
            if (Exact.TryGetValue(source, out translated))
                return translated;

            string normalized = Normalize(source);
            if (Normalized.TryGetValue(normalized, out translated))
                return translated;

            if (ShortUiTerms.TryGetValue(normalized, out translated))
                return translated;

            return TranslateCompositeText(source);
        }

        private static string TranslateCompositeText(string source)
        {
            if (String.IsNullOrEmpty(source))
                return source;

            string result = source;

            const string translatedLookPrefix = "당신은 봅니다:";
            if (result.StartsWith(translatedLookPrefix, StringComparison.Ordinal))
            {
                string objectName = StripLeadingEnglishArticle(
                    result.Substring(translatedLookPrefix.Length).Trim());
                if (objectName.EndsWith(".", StringComparison.Ordinal))
                    objectName = objectName.Substring(0, objectName.Length - 1).TrimEnd();
                if (ContainsKorean(objectName))
                    return "당신은 " + objectName + GetObjectParticle(objectName) + " 봅니다.";
            }

            const string extinguishPrefix = "You extinguish your ";
            if (result.StartsWith(extinguishPrefix, StringComparison.OrdinalIgnoreCase))
            {
                string itemName = StripLeadingEnglishArticle(
                    result.Substring(extinguishPrefix.Length).Trim());
                if (itemName.EndsWith(".", StringComparison.Ordinal))
                    itemName = itemName.Substring(0, itemName.Length - 1).TrimEnd();
                if (ContainsKorean(itemName))
                    return itemName + GetObjectParticle(itemName) + " 껐습니다.";
            }

            const string translatedExtinguishPrefix = "당신은 다음을 껐습니다:";
            if (result.StartsWith(translatedExtinguishPrefix, StringComparison.Ordinal))
            {
                string itemName = StripLeadingEnglishArticle(
                    result.Substring(translatedExtinguishPrefix.Length).Trim());
                if (itemName.EndsWith(".", StringComparison.Ordinal))
                    itemName = itemName.Substring(0, itemName.Length - 1).TrimEnd();
                if (ContainsKorean(itemName))
                    return itemName + GetObjectParticle(itemName) + " 껐습니다.";
            }

            // Food taste messages are assembled without a separator:
            // "That " + translated item name + translated taste sentence.
            // Rebuild them in Korean word order, including the topic particle.
            string foodMessage = TranslateFoodTasteMessage(result);
            if (foodMessage != result)
                return foodMessage;

            const string lockedSuffix = " is locked.";
            if (result.StartsWith("The ", StringComparison.OrdinalIgnoreCase) &&
                result.EndsWith(lockedSuffix, StringComparison.OrdinalIgnoreCase))
            {
                string subject = result.Substring(
                    4, result.Length - 4 - lockedSuffix.Length).Trim();
                if (ContainsKorean(subject))
                    return subject + GetSubjectParticle(subject) + " 잠겨 있습니다.";
            }

            // Equipment-destruction messages are assembled at runtime after the
            // item name has already been translated, e.g. "Your 가죽 각반 was destroyed.".
            const string possessivePrefix = "Your ";
            const string destroyedSuffix = " was destroyed.";
            if (result.StartsWith(possessivePrefix, StringComparison.OrdinalIgnoreCase) &&
                result.EndsWith(destroyedSuffix, StringComparison.OrdinalIgnoreCase))
            {
                string itemName = result.Substring(
                    possessivePrefix.Length,
                    result.Length - possessivePrefix.Length - destroyedSuffix.Length).Trim();
                if (ContainsKorean(itemName))
                    return itemName + GetSubjectParticle(itemName) + " 파괴되었습니다.";
            }

            // Status-book sentences are assembled from translated values and English glue text.
            result = result.Replace("You guess that it is currently ", "현재 시각은 ");
            result = result.Replace("You are on the ", "현재 위치는 ");
            result = result.Replace("It is the ", "오늘은 ");
            result = result.Replace("You are ", "현재 상태: ");

            // Status and skill sheets are assembled as one formatted IMGUI string.
            // Depending on the selected font/style, their labels are separated from
            // the values by tabs or spaces rather than a colon, so translate the
            // label itself instead of matching only the colon form.
            result = result.Replace("Strength", "힘");
            result = result.Replace("Dexterity", "민첩");
            result = result.Replace("Intellect", "지능");
            result = result.Replace("Vitality", "활력");
            result = result.Replace("Experience", "경험치");
            result = result.Replace("Attack", "공격");
            result = result.Replace("Defense", "방어");
            result = result.Replace("Mana", "마나");
            result = result.Replace("Casting", "주문 시전");
            result = result.Replace("Skill points", "기술 점수");

            // English conjunctions can remain between already translated status
            // fragments (for example, "배부름 and 완전히 깨어 있음").
            if (ContainsKorean(result))
                result = result.Replace(" and ", " 그리고 ");

            result = RemoveEnglishArticlesBeforeKorean(result);

            return result;
        }

        private static string RemoveEnglishArticlesBeforeKorean(string value)
        {
            string[] lines = value.Replace("\r\n", "\n").Split('\n');
            bool changed = false;
            for (int i = 0; i < lines.Length; i++)
            {
                string line = lines[i];
                int start = 0;
                while (start < line.Length && Char.IsWhiteSpace(line[start]))
                    start++;

                int articleLength = 0;
                if (line.IndexOf("an ", start, StringComparison.OrdinalIgnoreCase) == start)
                    articleLength = 3;
                else if (line.IndexOf("a ", start, StringComparison.OrdinalIgnoreCase) == start)
                    articleLength = 2;

                if (articleLength == 0)
                    continue;

                string remainder = line.Substring(start + articleLength);
                if (!ContainsKorean(remainder))
                    continue;

                lines[i] = line.Substring(0, start) + remainder;
                changed = true;
            }
            return changed ? String.Join("\n", lines) : value;
        }

        private static string TranslateFoodTasteMessage(string value)
        {
            if (String.IsNullOrEmpty(value))
                return value;

            int prefixLength;
            if (value.StartsWith("That ", StringComparison.OrdinalIgnoreCase))
                prefixLength = 5;
            else if (value.StartsWith("그것 ", StringComparison.Ordinal))
                prefixLength = 3;
            else
                return value;

            string remainder = value.Substring(prefixLength).TrimStart();
            string[] koreanTasteSuffixes = {
                "맛이 썩 좋지 않았다.",
                "맛이 약간 상해 있었다.",
                "맛이 밋밋했다.",
                "맛이 꽤 괜찮았다.",
                "맛이 아주 훌륭했다."
            };
            string[] englishTasteSuffixes = {
                "tasted putrid.",
                "tasted a little rancid.",
                "tasted kind of bland.",
                "tasted pretty good.",
                "tasted great."
            };

            for (int i = 0; i < koreanTasteSuffixes.Length; i++)
            {
                string matchedSuffix = null;
                if (remainder.EndsWith(koreanTasteSuffixes[i], StringComparison.Ordinal))
                    matchedSuffix = koreanTasteSuffixes[i];
                else if (remainder.EndsWith(
                    englishTasteSuffixes[i], StringComparison.OrdinalIgnoreCase))
                    matchedSuffix = englishTasteSuffixes[i];

                if (matchedSuffix == null)
                    continue;

                string foodName = remainder.Substring(
                    0, remainder.Length - matchedSuffix.Length).Trim();
                if (ContainsKorean(foodName))
                    return foodName + GetTopicParticle(foodName) + " " +
                        koreanTasteSuffixes[i];
            }

            return value;
        }

        private static string StripLeadingEnglishArticle(string value)
        {
            if (String.IsNullOrEmpty(value))
                return value;

            if (value.StartsWith("an ", StringComparison.OrdinalIgnoreCase))
                return value.Substring(3).TrimStart();
            if (value.StartsWith("a ", StringComparison.OrdinalIgnoreCase))
                return value.Substring(2).TrimStart();
            if (value.StartsWith("an:", StringComparison.OrdinalIgnoreCase))
                return value.Substring(3).TrimStart();
            if (value.StartsWith("a:", StringComparison.OrdinalIgnoreCase))
                return value.Substring(2).TrimStart();
            return value;
        }

        private static void CreateKoreanFonts()
        {
            defaultUiFont = CreateRuntimeFont("Malgun Gothic", "기본 UI");

            if (defaultUiFont == null)
                defaultUiFont = CreateRuntimeFont("맑은 고딕", "기본 UI 예비");
            // Warhaven corrupts Unity 6 legacy IMGUI's dynamic glyph cache and
            // causes every label to reuse the main-menu "v2.1" glyph texture.
            characterFont = defaultUiFont;
        }

        private static Font CreateRuntimeFont(string familyName, string role)
        {
            try
            {
                Font font = Font.CreateDynamicFontFromOSFont(familyName, 32);
                if (font == null)
                {
                    Log.LogError(role + " 폰트를 만들 수 없습니다: " + familyName);
                    return null;
                }

                font.RequestCharactersInTexture("가나다라마바사아자차카타파하", 32);
                if (!font.HasCharacter('\uac00'))
                {
                    Log.LogError(role + " 폰트에 한글 글리프가 없습니다: " + familyName);
                    return null;
                }

                Log.LogInfo(role + " 폰트 준비 완료: " + familyName);
                return font;
            }
            catch (Exception ex)
            {
                Log.LogError(role + " 폰트 생성 실패 (" + familyName + "): " + ex.Message);
                return null;
            }
        }

        private static void TryCreateTmpFont()
        {
            if (defaultUiFont == null || koreanTmpFont != null)
                return;

            try
            {
                TMP_Settings.LoadDefaultSettings();
                TMP_FontAsset created = TMP_FontAsset.CreateFontAsset(
                    "Malgun Gothic", "Regular", 90);
                if (created == null)
                    return;

                created.name = "UnityUndergroundKoreanFallback";
                koreanTmpFont = created;
                Log.LogInfo("TextMeshPro Korean fallback font is ready.");
            }
            catch (Exception ex)
            {
                // TextMeshPro shaders and settings may not be initialized during early frames.
                // Update() retries after the game finishes loading its UI resources.
                if (!loggedTmpFontFailure)
                {
                    loggedTmpFontFailure = true;
                    Log.LogWarning("Deferred TextMeshPro font creation failed: " + ex);
                }
            }
        }

        private static void InstallPatches()
        {
            Harmony harmony = new Harmony("kr.ultima-underworld.korean.runtime");
            HarmonyMethod prefix = new HarmonyMethod(typeof(KoreanPlugin), "TranslateFirstStringArgument");

            TryPatch(harmony, AccessTools.PropertySetter(typeof(Text), "text"), prefix);
            TryPatch(harmony, AccessTools.PropertySetter(typeof(TMP_Text), "text"), prefix);
            TryPatch(harmony, AccessTools.PropertySetter(typeof(GUIContent), "text"), prefix);

            foreach (MethodInfo method in typeof(GUIContent).GetMethods(
                BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic))
            {
                ParameterInfo[] parameters = method.GetParameters();
                if (method.Name == "Temp" && parameters.Length > 0 && parameters[0].ParameterType == typeof(string))
                    TryPatch(harmony, method, prefix);
            }

            MethodInfo[] tmpMethods = typeof(TMP_Text).GetMethods(
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            foreach (MethodInfo method in tmpMethods)
            {
                ParameterInfo[] parameters = method.GetParameters();
                if (method.Name == "SetText" && parameters.Length > 0 && parameters[0].ParameterType == typeof(string))
                    TryPatch(harmony, method, prefix);
            }

            string[] loaderTypes = { "StringLoader", "DataLoader" };
            HarmonyMethod postfix = new HarmonyMethod(typeof(KoreanPlugin), "TranslateStringResult");
            foreach (string typeName in loaderTypes)
            {
                Type type = AccessTools.TypeByName(typeName);
                if (type == null)
                    continue;

                foreach (MethodInfo method in type.GetMethods(
                    BindingFlags.Static | BindingFlags.Instance | BindingFlags.Public |
                    BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
                {
                    if (method.ReturnType == typeof(string))
                        TryPatch(harmony, method, null, postfix);
                }
            }

            PatchCreateCharacterGui(harmony);
            PatchTutorialGui(harmony);
            PatchCutsceneGui(harmony);
            PatchGameMessages(harmony);
            PatchActionTextGetters(harmony);
        }

        private static void PatchCutsceneGui(Harmony harmony)
        {
            Type type = AccessTools.TypeByName("CutscenePlayer");
            if (type == null)
                return;

            MethodInfo onGui = AccessTools.Method(type, "OnGUI");
            TryPatch(harmony, onGui,
                new HarmonyMethod(typeof(KoreanPlugin), "PrepareCutsceneGui"));
        }

        private static void PatchActionTextGetters(Harmony harmony)
        {
            Assembly gameAssembly = null;
            foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                if (assembly.GetName().Name == "Assembly-CSharp")
                {
                    gameAssembly = assembly;
                    break;
                }
            }
            if (gameAssembly == null)
                return;

            HarmonyMethod postfix = new HarmonyMethod(typeof(KoreanPlugin), "TranslateStringResult");
            foreach (Type type in gameAssembly.GetTypes())
            {
                foreach (MethodInfo method in type.GetMethods(
                    BindingFlags.Instance | BindingFlags.Static | BindingFlags.Public |
                    BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
                {
                    if (method.ReturnType == typeof(string) &&
                        (method.Name == "GetUseText" || method.Name == "GetLookText"))
                        TryPatch(harmony, method, null, postfix);
                }
            }
        }

        private static void PatchGameMessages(Harmony harmony)
        {
            Type type = AccessTools.TypeByName("Messages");
            if (type == null)
                return;

            foreach (MethodInfo method in type.GetMethods(
                BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
            {
                ParameterInfo[] parameters = method.GetParameters();
                if (method.Name == "Add" && parameters.Length > 0 && parameters[0].ParameterType == typeof(string))
                    TryPatch(harmony, method,
                        new HarmonyMethod(typeof(KoreanPlugin), "TranslateGameMessage"));
            }
        }

        private static void PatchCreateCharacterGui(Harmony harmony)
        {
            Type type = AccessTools.TypeByName("CreateCharacter");
            if (type == null)
                return;

            foreach (MethodInfo method in type.GetMethods(
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
            {
                ParameterInfo[] parameters = method.GetParameters();
                if (method.Name == "GuiLabel" && parameters.Length == 4)
                    TryPatch(harmony, method, new HarmonyMethod(typeof(KoreanPlugin), "TranslateShortGuiLabel"));
                else if (method.Name == "GuiLabel" && parameters.Length == 6)
                    TryPatch(harmony, method, new HarmonyMethod(typeof(KoreanPlugin), "TranslateLongGuiLabel"));
                else if (method.Name == "GuiButton" && parameters.Length == 4)
                    TryPatch(harmony, method, new HarmonyMethod(typeof(KoreanPlugin), "TranslateGuiButton"));
                else if (method.Name == "OnGUI" && parameters.Length == 0)
                    TryPatch(harmony, method, new HarmonyMethod(typeof(KoreanPlugin), "PrepareCreateCharacterGui"));
            }
        }

        private static void PatchTutorialGui(Harmony harmony)
        {
            Type type = AccessTools.TypeByName("TutorialManager");
            if (type == null)
                return;

            foreach (MethodInfo method in type.GetMethods(
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
            {
                ParameterInfo[] parameters = method.GetParameters();
                if (method.Name == "BuildStepText" && method.ReturnType == typeof(string))
                    TryPatch(harmony, method, null,
                        new HarmonyMethod(typeof(KoreanPlugin), "TranslateStringResult"));
                else if (method.Name == "OnGUI" && parameters.Length == 0)
                    TryPatch(harmony, method,
                        new HarmonyMethod(typeof(KoreanPlugin), "PrepareTutorialGui"));
            }
        }

        private static void TryPatch(Harmony harmony, MethodInfo original, HarmonyMethod prefix)
        {
            TryPatch(harmony, original, prefix, null);
        }

        private static void TryPatch(Harmony harmony, MethodInfo original, HarmonyMethod prefix, HarmonyMethod postfix)
        {
            if (original == null)
                return;

            try
            {
                harmony.Patch(original, prefix, postfix);
            }
            catch (Exception ex)
            {
                Log.LogWarning("Could not patch " + original.DeclaringType.FullName + "." + original.Name + ": " + ex.Message);
            }
        }

        public static void TranslateFirstStringArgument(ref string __0)
        {
            __0 = Translate(__0);
        }

        public static void TranslateStringResult(ref string __result)
        {
            __result = Translate(__result);
        }

        public static void TranslateGameMessage(ref string __0)
        {
            string translated = Translate(__0);
            if (translated != __0)
            {
                __0 = translated;
                return;
            }

            const string lookPrefix = "You see ";
            if (__0 == null || !__0.StartsWith(lookPrefix, StringComparison.OrdinalIgnoreCase))
                return;

            string objectName = __0.Substring(lookPrefix.Length).Trim();
            objectName = StripLeadingEnglishArticle(objectName);
            if (objectName.EndsWith(".", StringComparison.Ordinal))
                objectName = objectName.Substring(0, objectName.Length - 1).TrimEnd();
            if (!ContainsKorean(objectName))
                return;

            __0 = "당신은 " + objectName + GetObjectParticle(objectName) + " 봅니다.";
        }

        private static string GetObjectParticle(string value)
        {
            for (int i = value.Length - 1; i >= 0; i--)
            {
                char c = value[i];
                if (c >= '\uac00' && c <= '\ud7a3')
                    return ((c - '\uac00') % 28) == 0 ? "를" : "을";
            }
            return "을(를)";
        }

        private static string GetSubjectParticle(string value)
        {
            for (int i = value.Length - 1; i >= 0; i--)
            {
                char c = value[i];
                if (c >= '\uac00' && c <= '\ud7a3')
                    return ((c - '\uac00') % 28) == 0 ? "가" : "이";
            }
            return "이(가)";
        }

        private static string GetTopicParticle(string value)
        {
            for (int i = value.Length - 1; i >= 0; i--)
            {
                char c = value[i];
                if (c >= '\uac00' && c <= '\ud7a3')
                    return ((c - '\uac00') % 28) == 0 ? "는" : "은";
            }
            return "은(는)";
        }

        public static void TranslateShortGuiLabel(ref string __2, GUIStyle __3)
        {
            __2 = Translate(__2);
            ApplyCharacterGuiFont(__3, __2);
        }

        public static void TranslateLongGuiLabel(ref string __4, GUIStyle __5)
        {
            __4 = Translate(__4);
            ApplyCharacterGuiFont(__5, __4);
        }

        public static void TranslateGuiButton(ref string __2)
        {
            __2 = Translate(__2);
        }

        public static void PrepareCreateCharacterGui(object __instance)
        {
            if (__instance == null || characterFont == null)
                return;

            string[] styleFields = {
                "labelStyle", "highlightedLabelStyle", "buttonStyle",
                "selectedButtonStyle", "descriptionStyle"
            };
            Type type = __instance.GetType();
            foreach (string fieldName in styleFields)
            {
                FieldInfo field = AccessTools.Field(type, fieldName);
                GUIStyle style = field == null ? null : field.GetValue(__instance) as GUIStyle;
                if (style != null)
                    style.font = characterFont;
            }
        }

        public static void PrepareTutorialGui(object __instance)
        {
            if (__instance == null || defaultUiFont == null)
                return;

            FieldInfo field = AccessTools.Field(__instance.GetType(), "textStyle");
            GUIStyle style = field == null ? null : field.GetValue(__instance) as GUIStyle;
            if (style != null)
                style.font = defaultUiFont;
        }

        public static void PrepareCutsceneGui(object __instance)
        {
            if (__instance == null)
                return;

            Type type = __instance.GetType();
            FieldInfo subtitlesField = AccessTools.Field(type, "voiceSubs");
            string[] subtitles = subtitlesField == null
                ? null
                : subtitlesField.GetValue(__instance) as string[];
            if (subtitles != null)
            {
                for (int i = 0; i < subtitles.Length; i++)
                    subtitles[i] = Translate(subtitles[i]);
            }

            if (defaultUiFont == null)
                return;

            FieldInfo fontField = AccessTools.Field(type, "font");
            if (fontField != null)
                fontField.SetValue(__instance, defaultUiFont);
        }

        private static void ApplyCharacterGuiFont(GUIStyle style, string value)
        {
            if (style != null && characterFont != null && ContainsKorean(value))
                style.font = characterFont;
        }

        private static bool ContainsKorean(string value)
        {
            if (String.IsNullOrEmpty(value))
                return false;

            foreach (char c in value)
            {
                if (c >= '\uac00' && c <= '\ud7a3')
                    return true;
            }
            return false;
        }

        private static void ScanVisibleText()
        {
            Text[] uiTexts = Resources.FindObjectsOfTypeAll<Text>();
            foreach (Text text in uiTexts)
            {
                if (text == null)
                    continue;

                string translated = Translate(text.text);
                if (translated != text.text)
                    text.text = translated;

                if (defaultUiFont != null && ContainsKorean(text.text) &&
                    (text.font == null || !text.font.HasCharacter('\uac00')))
                    text.font = defaultUiFont;
            }

            TMP_Text[] tmpTexts = Resources.FindObjectsOfTypeAll<TMP_Text>();
            foreach (TMP_Text text in tmpTexts)
            {
                if (text == null)
                    continue;

                string translated = Translate(text.text);
                if (translated != text.text)
                    text.text = translated;

                AddTmpFallback(text.font);
            }
        }

        private static void AddTmpFallback(TMP_FontAsset font)
        {
            if (koreanTmpFont == null || font == null || font == koreanTmpFont)
                return;

            int id = font.GetInstanceID();
            if (FontsWithFallback.Contains(id))
                return;

            FontsWithFallback.Add(id);
            if (font.fallbackFontAssetTable == null)
                font.fallbackFontAssetTable = new List<TMP_FontAsset>();
            if (!font.fallbackFontAssetTable.Contains(koreanTmpFont))
                font.fallbackFontAssetTable.Add(koreanTmpFont);
        }
    }
}
