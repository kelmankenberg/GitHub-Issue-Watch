import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import qs.Commons
import qs.Commons as Commons
import "."

Controls.ScrollView {
  id: root
  property real maximumHeight: Style.space(700)
  signal browseRequested(string url)
  readonly property var intervals: Reports.data.refreshOptions
  readonly property var scheduleLabels: intervals.map(function(minutes) {
    if (minutes === 0) return strings.t("schedule.manual")
    if (minutes >= 60) return strings.tn("schedule.hours", minutes / 60)
      .arg(Commons.I18n.formatNumber(minutes / 60))
    return strings.tn("schedule.minutes", minutes).arg(Commons.I18n.formatNumber(minutes))
  })

  implicitHeight: Math.min(settingsContent.implicitHeight, Math.max(Style.space(100), maximumHeight))
  contentWidth: availableWidth
  clip: true

  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  ColumnLayout {
    id: settingsContent
    width: root.availableWidth
    spacing: Style.space(10)

    PlainText {
      text: strings.t("settings.refresh")
      font.bold: true
    }
    Controls.ComboBox {
      objectName: "refreshSchedule"
      Layout.fillWidth: true
      model: root.scheduleLabels
      currentIndex: root.intervals.indexOf(Reports.data.automatic ? Reports.data.refreshMinutes : 0)
      enabled: Reports.loaded && !Reports.busy
      onActivated: function(index) { Reports.run(["schedule", String(root.intervals[index])]) }
    }
    PlainText {
      Layout.fillWidth: true
      text: strings.t("settings.scheduleHint")
      wrapMode: Text.Wrap
      opacity: 0.7
      font.pixelSize: Style.font.bodySmall
    }
    PlainText {
      text: strings.t("settings.notifications")
      font.bold: true
    }
    Controls.CheckBox {
      objectName: "badgePreference"
      text: strings.t("settings.badge")
      checked: Reports.data.badgeEnabled
      enabled: Reports.loaded && !Reports.busy
      onClicked: Reports.run(["badge", checked ? "on" : "off"])
    }
    Controls.CheckBox {
      objectName: "desktopPreference"
      text: strings.t("settings.desktop")
      checked: Reports.data.desktopNotifications
      enabled: Reports.loaded && !Reports.busy
      onClicked: Reports.run(["notifications", checked ? "on" : "off"])
    }
    PlainText {
      Layout.fillWidth: true
      text: strings.t("settings.notificationHelp")
      wrapMode: Text.Wrap
      opacity: 0.7
      font.pixelSize: Style.font.bodySmall
    }
    PlainText {
      text: strings.t("settings.account")
      font.bold: true
    }
    PlainText {
      Layout.fillWidth: true
      text: Reports.data.owner ? strings.t("scope").arg(Reports.data.owner) : strings.t("connecting")
      wrapMode: Text.Wrap
    }
    PlainText {
      Layout.fillWidth: true
      text: strings.t("account.notice")
      wrapMode: Text.Wrap
      font.pixelSize: Style.font.bodySmall
    }
    PlainText {
      Layout.fillWidth: true
      text: strings.t("account.setup")
      wrapMode: Text.Wrap
      font.pixelSize: Style.font.bodySmall
      opacity: 0.7
    }
    PlainText {
      text: strings.t("settings.help")
      font.bold: true
    }
    RowLayout {
      Layout.fillWidth: true
      spacing: Style.space(8)
      Controls.Button {
        objectName: "reportPluginBug"
        Layout.fillWidth: true
        text: strings.t("feedback.bug")
        onClicked: root.browseRequested("https://github.com/kelmankenberg/OmaRepoReport/issues/new?template=bug_report.yml")
      }
      Controls.Button {
        objectName: "requestPluginFeature"
        Layout.fillWidth: true
        text: strings.t("feedback.feature")
        onClicked: root.browseRequested("https://github.com/kelmankenberg/OmaRepoReport/issues/new?template=feature_request.yml")
      }
    }
    Controls.Button {
      Layout.fillWidth: true
      text: strings.t("settings.repository")
      onClicked: root.browseRequested("https://github.com/kelmankenberg/OmaRepoReport")
    }
    PlainText {
      Layout.fillWidth: true
      text: strings.t("settings.feedbackHint")
      wrapMode: Text.Wrap
      opacity: 0.7
      font.pixelSize: Style.font.bodySmall
    }
    PlainText {
      text: strings.t("settings.version").arg(Reports.data.pluginVersion)
      opacity: 0.7
      font.pixelSize: Style.font.bodySmall
    }
  }
}
