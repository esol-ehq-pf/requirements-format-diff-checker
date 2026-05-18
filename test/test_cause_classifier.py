"""test_cause_classifier.py

cause_classifier.py の各マッチャーの単体テスト。

実行:
    cd work/format-change
    pytest test/test_cause_classifier.py -v
"""

import sys
from pathlib import Path

# スクリプトのパスを通す
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import cause_classifier as cc

# ─────────────────────────── ヘルパー ────────────────────────────

SWC_NODE_MAP = {
    "AhbAhs": "Main",
    "FcmRc": ["DataLatchGsp4C1", "DataLatchGsp4C2",
               "DataLatchGsp4C3", "DataLatchGsp4C4",
               "PreDataLatchForInlyrC1", "PreDataLatchForInlyrC2",
               "PreDataLatchForInlyrC3", "PreDataLatchForInlyrC4"],
    "InlyrBsr": ["InlyrBsr(C1C3)", "InlyrBsr(C2C4)"],
    "IoProxy": ["InlyrBsrProxy", "InlyrFrdProxy", "InlyrFsrProxy",
                "InlyrGlProxy", "OutlyrProxy"],
    "Preempt": ["b2m_spi_1st_IO_recv", "viddraw"],
    "SplAd": ["CSpm", "EventSpm", "MapEnd", "Rob", "TrafficJamSupport", "Ymv"],
}

BUDGET_ALIAS_MAP = {
    "AhbAhs": "Main",
    "LgtCtl": "LightingControl",
    "TJSupport": "TrafficJamSupport",
    "PsFsn": "ApFsn",
}


def classify(file_name, diff_type, old_val, new_val):
    """テスト用 wrapper: (cause_tag, level, pattern_no) を返す。"""
    applicable = cc.get_applicable_matchers(file_name)
    return cc.classify_detail(
        file_name=file_name,
        diff_type=diff_type,
        old_val=old_val,
        new_val=new_val,
        applicable_matchers=applicable,
        swc_node_map=SWC_NODE_MAP,
        budget_alias_map=BUDGET_ALIAS_MAP,
    )


# ─────────────────────────── M-01 ────────────────────────────────

class TestM01:
    def test_lowercase_no_bracket(self):
        cause, level, mid = classify(
            "before_requirements.csv", "RequirementOwnerの変化", "VidDraw", "viddraw"
        )
        assert cause == "chksimyml(2-③)"
        assert level == "G-1"
        assert mid == "M-01"

    def test_lowercase_with_bracket(self):
        """括弧あり → infsimyml(1-①)"""
        cause, level, mid = classify(
            "temp/after_cpuload_requirements.csv", "RequirementOwnerの変化",
            "PF_1msTask(2SoC, Base)", "pf_1mstask"
        )
        assert cause == "infsimyml(1-①)"
        assert mid == "M-01"

    def test_no_match_different_value(self):
        """括弧除去後も一致しない → M-01 非マッチ"""
        cause, _, mid = classify(
            "before_requirements.csv", "RequirementOwnerの変化", "VidDraw", "VidDraw2"
        )
        assert mid != "M-01"


# ─────────────────────────── M-02 ────────────────────────────────

class TestM02:
    def test_self_reference_no_bracket(self):
        """X → X/X（括弧なし）"""
        cause, level, mid = classify(
            "before_requirements.csv", "RequirementOwnerの変化", "AhbAhs", "AhbAhs/AhbAhs"
        )
        assert cause == "chksimyml(2-①)"
        assert mid == "M-02"

    def test_self_reference_with_bracket(self):
        """X(sfx) → normalize(X)/X(sfx)   例: InlyrBsr(C1C3) → InlyrBsr/InlyrBsr(C1C3)"""
        cause, level, mid = classify(
            "before_requirements.csv", "RequirementOwnerの変化",
            "InlyrBsr(C1C3)", "InlyrBsr/InlyrBsr(C1C3)"
        )
        assert cause == "chksimyml(2-①)"
        assert mid == "M-02"


# ─────────────────────────── M-03 ────────────────────────────────

class TestM03:
    def test_preempt_prefix(self):
        """X → Preempt/X"""
        cause, level, mid = classify(
            "before_requirements.csv", "Sequence/Sender/Receiver/FirstTask/SecondTaskの変化",
            "b2m_spi_1st_IO_recv", "Preempt/b2m_spi_1st_IO_recv"
        )
        assert cause == "chksimyml(2-①)"
        assert mid == "M-03"


# ─────────────────────────── M-04 ────────────────────────────────

class TestM04:
    def test_task_id_added(self):
        cause, level, mid = classify(
            "temp/after_cpuload_requirements.csv", "TaskIDの追加", "-", "PF_window1"
        )
        assert cause == "infsimyml(1-③)"
        assert mid == "M-04"


# ─────────────────────────── M-05 ────────────────────────────────

class TestM05:
    def test_target_key_added(self):
        cause, level, mid = classify(
            "before_requirements.csv", "キーの追加", "-", "Target: SomeSWC"
        )
        assert cause == "chksimyml(2-②)"
        assert mid == "M-05"

    def test_no_target_in_new(self):
        cause, _, mid = classify(
            "before_requirements.csv", "キーの追加", "-", "OtherKey: value"
        )
        assert mid != "M-05"


# ─────────────────────────── M-06 ────────────────────────────────

class TestM06:
    def test_tool_tag_to_branch(self):
        cause, level, mid = classify(
            "input_info.txt", "etcの変化",
            "Tool Tag: some-tag", "Tool Branch: main"
        )
        assert "ver3" in cause.lower() or "slot" in cause.lower()
        assert mid == "M-06"


# ─────────────────────────── M-08 ────────────────────────────────

class TestM08:
    def test_bracket_removal_simple(self):
        """ViewMo(m01_m02) → ViewMo"""
        cause, level, mid = classify(
            "before_budget.csv", "TaskListの変化", "ViewMo(m01_m02)", "ViewMo"
        )
        assert cause == "budget.yaml(4-②A)"
        assert mid == "M-08"

    def test_no_match_splad(self):
        """SplAd( で始まる場合は M-08 非マッチ"""
        cause, _, mid = classify(
            "before_budget.csv", "TaskListの変化", "SplAd(EventSpm)", "EventSpm"
        )
        assert mid != "M-08"


# ─────────────────────────── M-09 ────────────────────────────────

class TestM09:
    def test_splad_direct(self):
        """SplAd(EventSpm) → EventSpm（直接一致）"""
        cause, level, mid = classify(
            "before_budget.csv", "TaskListの変化", "SplAd(EventSpm)", "EventSpm"
        )
        assert cause == "budget.yaml(4-②B)"
        assert mid == "M-09"

    def test_splad_no_match_alias(self):
        """SplAd(TJSupport) → TrafficJamSupport（M-09 非マッチ → M-14 に委ねる）"""
        cause, _, mid = classify(
            "before_budget.csv", "TaskListの変化", "SplAd(TJSupport)", "TrafficJamSupport"
        )
        assert mid != "M-09"


# ─────────────────────────── M-10 ────────────────────────────────

class TestM10:
    def test_pf1ms_base_loss(self):
        cause, level, mid = classify(
            "input_data_ba.csv", "pf_1ms_base行の消失", "-", "node=pf_1ms_base の行が消失"
        )
        assert cause == "ツール起因(21/23)"
        assert mid == "M-10"

    def test_pf1ms_mid_loss(self):
        cause, level, mid = classify(
            "input_data_igr.csv", "pf_1ms_mid行の消失", "-", "node=pf_1ms_mid の行が消失"
        )
        assert cause == "ツール起因(21/23)"
        assert mid == "M-10"


# ─────────────────────────── M-11 ────────────────────────────────

class TestM11:
    def test_nodename_pf1ms(self):
        cause, level, mid = classify(
            "processing_time_result.csv", "NodeNameの変化",
            "pf_1ms_base", "PF_1msTask(2SoC, Base)"
        )
        assert cause == "ツール起因(9/28)"
        assert mid == "M-11"


# ─────────────────────────── M-12 ────────────────────────────────

class TestM12:
    def test_swc_node_1to1(self):
        """AhbAhs → AhbAhs/Main"""
        cause, level, mid = classify(
            "before_requirements.csv", "RequirementOwnerの変化",
            "AhbAhs", "AhbAhs/Main"
        )
        assert cause == "chksimyml(2-①)"
        assert mid == "M-12"

    def test_swc_node_1ton(self):
        """FcmRc → FcmRc/DataLatchGsp4C1"""
        cause, level, mid = classify(
            "after_requirements.csv", "RequirementOwnerの変化",
            "FcmRc", "FcmRc/DataLatchGsp4C1"
        )
        assert cause == "chksimyml(2-①)"
        assert mid == "M-12"

    def test_no_match_unknown_swc(self):
        """未知 SWC → M-12 非マッチ"""
        cause, _, mid = classify(
            "before_requirements.csv", "RequirementOwnerの変化",
            "UnknownSWC", "UnknownSWC/SomeNode"
        )
        assert mid != "M-12"


# ─────────────────────────── M-13 ────────────────────────────────

class TestM13:
    def test_schedule_result(self):
        """schedule_result.csv の逆変換 → chksimyml(2-③)"""
        cause, level, mid = classify(
            "schedule_result.csv", "id/nameの変化",
            "LgtCtl/LightingControl", "LgtCtl"
        )
        assert cause == "chksimyml(2-③)"
        assert mid == "M-13"

    def test_after_requirements(self):
        """after_requirements.csv の逆変換 → ツール起因(18/30)"""
        cause, level, mid = classify(
            "temp/after_requirements.csv", "RequirementOwnerの変化",
            "AhbAhs/Main", "AhbAhs"
        )
        assert cause == "ツール起因(18/30)(要確認)"
        assert mid == "M-13"

    def test_before_requirements(self):
        """before_requirements.csv の逆変換 → ツール起因(19/31)"""
        cause, level, mid = classify(
            "temp/before_requirements.csv", "RequirementOwnerの変化",
            "AhbAhs/Main", "AhbAhs"
        )
        assert cause == "ツール起因(19/31)(要確認)"
        assert mid == "M-13"


# ─────────────────────────── M-14 ────────────────────────────────

class TestM14:
    def test_alias_simple(self):
        """AhbAhs(b01_m01_m02) → Main"""
        cause, level, mid = classify(
            "before_budget.csv", "TaskListの変化",
            "AhbAhs(b01_m01_m02)", "Main"
        )
        assert cause == "budget.yaml(4-②C)"
        assert mid == "M-14"

    def test_alias_splad_wrapper(self):
        """SplAd(TJSupport) → TrafficJamSupport（BUDGET_ALIAS_MAP 経由）"""
        cause, level, mid = classify(
            "before_budget.csv", "TaskListの変化",
            "SplAd(TJSupport)", "TrafficJamSupport"
        )
        assert cause == "budget.yaml(4-②C)"
        assert mid == "M-14"

    def test_psfsn_rename(self):
        """PsFsn(m01) → ApFsn（NP-4 対応）"""
        cause, level, mid = classify(
            "before_budget.csv", "TaskListの変化",
            "PsFsn(m01)", "ApFsn"
        )
        assert cause == "budget.yaml(4-②C)"
        assert mid == "M-14"


# ─────────────────────────── M-16 ────────────────────────────────

class TestM16:
    def test_node_order_change(self):
        cause, level, mid = classify(
            "input_data_ba.csv", "Nodeの順序入れ替わり",
            "-", "start_clock_msが同じnodeに対して，順序が入れ替わるケースあり(2016件)"
        )
        assert cause == "ツール起因(22/24)"
        assert mid == "M-16"


# ─────────────────────────── M-17 ────────────────────────────────

class TestM17:
    def test_tsync_pf1ms_loss(self):
        cause, level, mid = classify(
            "after_csv_data_tsync_PlusBA.csv", "pf_1ms_base行の消失",
            "-", "node=pf_1ms_base の行が消失"
        )
        assert cause == "ツール起因(パターン9/28の連鎖)"
        assert mid == "M-17"


# ─────────────────────────── M-18 ────────────────────────────────

class TestM18:
    def test_pf1ms_png_missing(self):
        cause, level, mid = classify(
            "processing_load_duration_graph/duration_of_PF_1msTask(2SoC, Base).png",
            "ファイル消失",
            "duration_of_PF_1msTask(2SoC, Base).png が存在する",
            "duration_of_PF_1msTask(2SoC, Base).png が存在しない",
        )
        assert cause == "ツール起因(パターン9/28の連鎖)"
        assert mid == "M-18"

    def test_non_pf1ms_png_no_match(self):
        """duration_of_PF_1msTask でない PNG は M-18 非マッチ"""
        cause, _, mid = classify(
            "Sequence_duration_graph/duration_of_VidDraw-01.png",
            "ファイル消失", "exists", "not exists",
        )
        assert mid != "M-18"


# ─────────────────────────── M-19 ────────────────────────────────

class TestM19:
    def test_png_title_change(self):
        cause, level, mid = classify(
            "Sequence_duration_graph/duration_of_VidDraw-01.png",
            "画像差分",
            "タイトルduration_of_VidDraw-01",
            "タイトルduration_of_viddraw-01に変化",
        )
        assert cause == "chksimyml(2-③)"
        assert mid == "M-19"


# ─────────────────────────── M-20 ────────────────────────────────

class TestM20:
    def test_anteroposterior_false_to_true(self):
        cause, level, mid = classify(
            "before_requirements.csv",
            "IsAnteroposteriorRelationFixedの変化",
            "IsAnteroposteriorRelationFixed: false",
            "IsAnteroposteriorRelationFixed: true",
        )
        assert cause == "chksimyml(2-①)"
        assert mid == "M-20"


class TestM21:
    def test_etc_change(self):
        cause, level, mid = classify(
            "schedule_result.csv",
            "etcの変化",
            "[viewrdr_cirend]start clock ms: 127164",
            "[Preempt:viewrdr_cirend]start clock ms: 127244",
        )
        assert cause == "chksimyml(2-①)"
        assert mid == "M-21"


# ─────────────────────────── ルーティング ────────────────────────────────

class TestRouting:
    def test_before_requirements(self):
        matchers = cc.get_applicable_matchers("temp/before_requirements.csv")
        assert "M-01" in matchers
        assert "M-02" in matchers
        assert "M-13" in matchers
        assert "M-20" in matchers

    def test_before_budget(self):
        matchers = cc.get_applicable_matchers("before_budget.csv")
        assert "M-08" in matchers
        assert "M-09" in matchers
        assert "M-14" in matchers
        assert "M-01" not in matchers

    def test_png(self):
        matchers = cc.get_applicable_matchers("processing_load_duration_graph/foo.png")
        assert "M-18" in matchers
        assert "M-19" in matchers

    def test_cpuload(self):
        matchers = cc.get_applicable_matchers("temp/after_cpuload_requirements.csv")
        assert "M-01" in matchers
        assert "M-04" in matchers
        assert "M-11" in matchers

    def test_schedule_result_has_m21(self):
        matchers = cc.get_applicable_matchers("schedule_result.csv")
        assert "M-01" in matchers
        assert "M-13" in matchers
        assert "M-20" in matchers
        assert "M-21" in matchers
