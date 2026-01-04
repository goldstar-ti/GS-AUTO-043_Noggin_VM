# Noggin Object Type Field Reference

This document provides a comprehensive reference for the business-specific fields in Noggin object types used for safety inspections and compliance checks.

## Table of Contents

- [Overview](#overview)
- [Standard Metadata Fields](#standard-metadata-fields)
- [Object Types](#object-types)
  - [Trailer Audits](#trailer-audits)
  - [Site Observations](#site-observations)
  - [Load Compliance Check (Supervisor/Manager)](#load-compliance-check-supervisormanager)
  - [Load Compliance Check (Driver/Loader)](#load-compliance-check-driverloader)
  - [Forklift Prestart Inspection](#forklift-prestart-inspection)
  - [Coupling Compliance Check](#coupling-compliance-check)
- [Fields by Category](#fields-by-category)

## Overview

This reference documents the field schemas for six Noggin object types:

- **Trailer Audits**: 35 business fields
- **Site Observations**: 28 business fields
- **Load Compliance Check (Supervisor/Manager)**: 122 business fields
- **Load Compliance Check (Driver/Loader)**: 35 business fields
- **Forklift Prestart Inspection**: 92 business fields
- **Coupling Compliance Check**: 51 business fields

All fields are optional unless explicitly marked as required. All objects include standard metadata fields in the `$meta` property.

## Standard Metadata Fields

All Noggin objects include a `$meta` property containing system-managed metadata. These fields are consistent across all object types and are primarily read-only.

| Field | Type | Read-Only | Description |
|-------|------|-----------|-------------|
| `createdDate` | string (date-time) | Yes | The datetime the object was first created |
| `modifiedDate` | string (date-time) | Yes | The datetime the object was last modified |
| `security` | string (tip) | No | The security policy applied to the object |
| `type` | string (tip) | Yes | The type definition of the object |
| `tip` | string (tip) | Yes | The object id |
| `sid` | string (sid) | Yes | The version id of the object |
| `branch` | string (tip) | Yes | The branch the version of the object is in |
| `parent` | array | Yes | The ids of the previous versions of the object |
| `errors` | array | Yes | The list of errors in this version of the object |

### Example $meta Object

```json
{
  "$meta": {
    "createdDate": "2025-01-04T10:30:00Z",
    "modifiedDate": "2025-01-04T14:45:00Z",
    "security": "security/policy123",
    "type": "type/objectTypeDefinition",
    "tip": "object/abc123def456",
    "sid": "version/xyz789",
    "branch": "branch/master",
    "parent": ["version/previous123"],
    "errors": []
  }
}
```

## Object Types

### Trailer Audits

**Schema Key**: `ObjectType_trailerAudits`

**Total Fields**: 35

**Required Fields**: None (all fields are optional)

#### Field Reference

| Field Name | Type | Example |
|------------|------|---------|
| `comments` | string (format: html) | "<p>Details here</p>" |
| `correctiveActions` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `date` | string (format: date) | "2025-01-04" |
| `driverComment` | string (format: html) | "<p>Details here</p>" |
| `driverPresentNo` | boolean | true / false |
| `driverPresentYes` | boolean | true / false |
| `externallyExcellent` | boolean | true / false |
| `externallyFair` | boolean | true / false |
| `externallyGood` | boolean | true / false |
| `externallyUnacceptable` | boolean | true / false |
| `fireExtinguisherNA` | boolean | true / false |
| `fireExtinguisherNo` | boolean | true / false |
| `fireExtinguisherYes` | boolean | true / false |
| `inspectedBy` | string (format: tip) (max length: 32766) | "object/ref123" |
| `internallyToolboxExcellent` | boolean | true / false |
| `internallyToolboxFair` | boolean | true / false |
| `internallyToolboxGood` | boolean | true / false |
| `internallyToolboxUnacceptable` | boolean | true / false |
| `loadRestraintEquipmentNA` | boolean | true / false |
| `loadRestraintEquipmentNo` | boolean | true / false |
| `loadRestraintEquipmentYes` | boolean | true / false |
| `noOfChains` | number | 5 |
| `noOfGluts` | number | 5 |
| `noOfWebbingStraps` | number | 5 |
| `rego` | string (format: tip) (max length: 32766) | "object/ref123" |
| `regularDriver` | string (format: tip) | "object/ref123" |
| `revolvingBeaconNA` | boolean | true / false |
| `revolvingBeaconNo` | boolean | true / false |
| `revolvingBeaconYes` | boolean | true / false |
| `spareTyreNA` | boolean | true / false |
| `spareTyreNo` | boolean | true / false |
| `spareTyreYes` | boolean | true / false |
| `team` | string (format: tip) | "team/logistics" |
| `trailerAuditId` | string (format: tip) (max length: 32766) | "object/ref123" |
| `vehicle` | string (format: tip) | "vehicle/abc123" |

### Site Observations

**Schema Key**: `ObjectType_siteObservations`

**Total Fields**: 28

**Required Fields**: None (all fields are optional)

#### Field Reference

| Field Name | Type | Example |
|------------|------|---------|
| `attachments1` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `attachments2` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `attachments3` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `attachments4` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `correctiveActions` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `date` | string (format: date) | "2025-01-04" |
| `department` | string (format: tip) | "object/ref123" |
| `details1` | string (format: html) | "<p>Details here</p>" |
| `details2` | string (format: html) | "<p>Details here</p>" |
| `details3` | string (format: html) | "<p>Details here</p>" |
| `details4` | string (format: html) | "<p>Details here</p>" |
| `findings1` | string (format: html) | "<p>Details here</p>" |
| `findings2` | string (format: html) | "<p>Details here</p>" |
| `findings3` | string (format: html) | "<p>Details here</p>" |
| `findings4` | string (format: html) | "<p>Details here</p>" |
| `inspectedBy` | string (format: tip) | "object/ref123" |
| `observation1Checkbox` | boolean | true / false |
| `observation2Checkbox` | boolean | true / false |
| `observation3Checkbox` | boolean | true / false |
| `observation4Checkbox` | boolean | true / false |
| `personInvolved` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `siteManager` | string (format: tip) | "object/ref123" |
| `siteObservationId` | string (format: tip) (max length: 32766) | "object/ref123" |
| `summary1` | string (format: html) | "<p>Details here</p>" |
| `summary2` | string (format: html) | "<p>Details here</p>" |
| `summary3` | string (format: html) | "<p>Details here</p>" |
| `summary4` | string (format: html) | "<p>Details here</p>" |
| `vehicleS` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |

### Load Compliance Check (Supervisor/Manager)

**Schema Key**: `ObjectType_loadComplianceCheckSupervisorManager`

**Total Fields**: 122

**Required Fields**: None (all fields are optional)

#### Field Reference

| Field Name | Type | Example |
|------------|------|---------|
| `additionalRestraintUsedForItemsText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `additionalRestraintUsedForItemsThatCanBeDislodgedF` | boolean | true / false |
| `additionalRestraintUsedForItemsThatCanBeDislodgedFN` | boolean | true / false |
| `additionalRestraintUsedForItemsThatCanBeDislodgedFNA` | boolean | true / false |
| `allLashingsAreAnchoredSecurelyToTheTrailerIEHooksNA` | boolean | true / false |
| `allLashingsAreAnchoredSecurelyToTheTrailerIEHooksNN` | boolean | true / false |
| `allLashingsAreAnchoredSecurelyToTheTrailerIEHooksNY` | boolean | true / false |
| `allLashingsAreAnchoredText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `allLashingsPositionedInLineWithDunnageAndBearersFoN` | boolean | true / false |
| `allLashingsPositionedInLineWithDunnageAndBearersFoNA` | boolean | true / false |
| `allLashingsPositionedInLineWithDunnageAndBearersFoY` | boolean | true / false |
| `allLashingsPositionedText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `allPalletsSkidsOrFramesAreInGoodConditionAndAbleToN` | boolean | true / false |
| `allPalletsSkidsOrFramesAreInGoodConditionAndAbleToNA` | boolean | true / false |
| `allPalletsSkidsOrFramesAreInGoodConditionAndAbleToY` | boolean | true / false |
| `allPalletsSkidsOrFramesText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `appropriateStrapAndOrProductProtectionIsInPlaceEGEN` | boolean | true / false |
| `appropriateStrapAndOrProductProtectionIsInPlaceEGENA` | boolean | true / false |
| `appropriateStrapAndOrProductProtectionIsInPlaceEGEY` | boolean | true / false |
| `appropriateStrapAndOrProductText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `attachments` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `chains` | boolean | true / false |
| `commentsActions` | string (format: html) | "<p>Details here</p>" |
| `contractorName` | string (format: tip) (max length: 32766) | "object/ref123" |
| `customerClient` | string (format: tip) | "object/ref123" |
| `dangerousGoodsLoadsHaveGatesInPlaceNA` | boolean | true / false |
| `dangerousGoodsLoadsHaveGatesInPlaceNo` | boolean | true / false |
| `dangerousGoodsLoadsHaveGatesInPlaceYes` | boolean | true / false |
| `dangerousGoodsLoadsText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `date` | string (format: date) | "2025-01-04" |
| `driverLoaderName` | string (format: tip) (max length: 32766) | "object/ref123" |
| `dunnageIsAlignedText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `dunnageIsAlignedWithSufficientClampDownForceToKeepN` | boolean | true / false |
| `dunnageIsAlignedWithSufficientClampDownForceToKeepNA` | boolean | true / false |
| `dunnageIsAlignedWithSufficientClampDownForceToKeepY` | boolean | true / false |
| `freeTextWhyIsTheLoadNotCompliant` | string (format: tip) (max length: 32766) | "object/ref123" |
| `gluts` | boolean | true / false |
| `goldstarOrContactorList` | string (format: tip) | "contact/user456" |
| `haveGalasCornersBeenAppliedToCoilsN` | boolean | true / false |
| `haveGalasCornersBeenAppliedToCoilsNa` | boolean | true / false |
| `haveGalasCornersBeenAppliedToCoilsText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `haveGalasCornersBeenAppliedToCoilsY` | boolean | true / false |
| `inspectedBy` | string (format: tip) (max length: 32766) | "object/ref123" |
| `isTheLoadCompliantWithTheLoadRestraintGuideN` | boolean | true / false |
| `isTheLoadCompliantWithTheLoadRestraintGuideY` | boolean | true / false |
| `jobNumber` | string (format: tip) (max length: 32766) | "object/ref123" |
| `lcsInspectionId` | string (format: tip) (max length: 32766) | "object/ref123" |
| `loadAreEitherSittingOnTimberRubberOrAntiSlipMateri` | boolean | true / false |
| `loadAreEitherSittingOnTimberRubberOrAntiSlipMateriN` | boolean | true / false |
| `loadAreEitherSittingOnTimberRubberOrAntiSlipMateriNA` | boolean | true / false |
| `loadAreEitherSittingText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `loadDistributedCorrectlyOverTheVehicleAxlesN` | boolean | true / false |
| `loadDistributedCorrectlyOverTheVehicleAxlesNa` | boolean | true / false |
| `loadDistributedCorrectlyOverTheVehicleAxlesY` | boolean | true / false |
| `loadDistributedCorrectlyText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `loadDoesNotExceedHeadboardHeightByMoreThanHalfTheT` | boolean | true / false |
| `loadDoesNotExceedHeadboardHeightByMoreThanHalfTheTN` | boolean | true / false |
| `loadDoesNotExceedHeadboardHeightByMoreThanHalfTheTNA` | boolean | true / false |
| `loadDoesNotExceedHeadboardText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `loadDoesNotExceedMassOrDimensionOverhangRequiremen` | boolean | true / false |
| `loadDoesNotExceedMassOrDimensionOverhangRequiremenNA` | boolean | true / false |
| `loadDoesNotExceedMassOrDimensionOverhangRequiremenY` | boolean | true / false |
| `loadDoesNotExceedMassText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `loadsAreNotToBeRestrainedAtLowLashingAngle30N` | boolean | true / false |
| `loadsAreNotToBeRestrainedAtLowLashingAngle30Na` | boolean | true / false |
| `loadsAreNotToBeRestrainedAtLowLashingAngle30Y` | boolean | true / false |
| `loadsAreNotToBeRestrainedText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `mass` | string (format: tip) (max length: 32766) | "object/ref123" |
| `noLooseItemsEGDunnageChainsStrapsEtcAreLeftOnTheLo` | boolean | true / false |
| `noLooseItemsEGDunnageChainsStrapsEtcAreLeftOnTheLoN` | boolean | true / false |
| `noLooseItemsEGDunnageChainsStrapsEtcAreLeftOnTheLoNA` | boolean | true / false |
| `noLooseItemsText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `noOfChains` | number | 5 |
| `noOfGluts` | number | 5 |
| `noOfStraps` | number | 5 |
| `noOfWebbings` | number | 5 |
| `noRectangularDunnageOnTheShortEdgeNA` | boolean | true / false |
| `noRectangularDunnageOnTheShortEdgeNo` | boolean | true / false |
| `noRectangularDunnageOnTheShortEdgeYes` | boolean | true / false |
| `noRectangularDunnageText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `numberOfLashingsText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `numberOfLashingsUsedAppropriateForTheLoadN` | boolean | true / false |
| `numberOfLashingsUsedAppropriateForTheLoadNa` | boolean | true / false |
| `numberOfLashingsUsedAppropriateForTheLoadY` | boolean | true / false |
| `palletJacksAreParkedAndSecuredNA` | boolean | true / false |
| `palletJacksAreParkedAndSecuredNo` | boolean | true / false |
| `palletJacksAreParkedAndSecuredYes` | boolean | true / false |
| `palletJacksAreParkedText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `productProtectionIsInPlaceToPreventScratchesAndProN` | boolean | true / false |
| `productProtectionIsInPlaceToPreventScratchesAndProNA` | boolean | true / false |
| `productProtectionIsInPlaceToPreventScratchesAndProY` | boolean | true / false |
| `productProtectionText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `restraintEquipmentInGoodWorkingConditionChainsTenNA` | boolean | true / false |
| `restraintEquipmentInGoodWorkingConditionChainsTensN` | boolean | true / false |
| `restraintEquipmentInGoodWorkingConditionChainsTensY` | boolean | true / false |
| `restraintEquipmentText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `runNumber` | string (format: tip) (max length: 32766) | "object/ref123" |
| `signature` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `straps` | boolean | true / false |
| `tailgatesSideAndCentrePinsAreSecuredToTheTrailerEGN` | boolean | true / false |
| `tailgatesSideAndCentrePinsAreSecuredToTheTrailerEGNA` | boolean | true / false |
| `tailgatesSideAndCentrePinsAreSecuredToTheTrailerEGY` | boolean | true / false |
| `tailgatesSideAndCentreText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `team` | string (format: tip) | "team/logistics" |
| `toolDuunageBoxesRacksSecuredNA` | boolean | true / false |
| `toolDuunageBoxesRacksSecuredNo` | boolean | true / false |
| `toolDuunageBoxesRacksSecuredYes` | boolean | true / false |
| `toolDuunageBoxesText` | string (format: tip) (max length: 32766) | "object/ref123" |
| `trailer` | string (format: tip) | "object/ref123" |
| `trailer2` | string (format: tip) | "object/ref123" |
| `trailer3` | string (format: tip) | "object/ref123" |
| `trailerId` | string (format: tip) (max length: 32766) | "object/ref123" |
| `trailerId2` | string (format: tip) (max length: 32766) | "object/ref123" |
| `trailerId3` | string (format: tip) (max length: 32766) | "object/ref123" |
| `vehicle` | string (format: tip) | "vehicle/abc123" |
| `vehicleId` | string (format: tip) (max length: 32766) | "vehicle/abc123" |
| `vehicleIsAppropriateForTheTaskIEMeetsMassDimension` | boolean | true / false |
| `vehicleIsAppropriateForTheTaskIEMeetsMassDimensionN` | boolean | true / false |
| `vehicleIsAppropriateForTheTaskIEMeetsMassDimensionNA` | boolean | true / false |
| `vehicleIsAppropriateForTheTaskText` | string (format: tip) (max length: 32766) | "vehicle/abc123" |
| `webbings` | boolean | true / false |
| `whichDepartmentDoesTheLoadBelongTo` | string (format: tip) | "object/ref123" |

### Load Compliance Check (Driver/Loader)

**Schema Key**: `ObjectType_loadComplianceCheckDriverLoader`

**Total Fields**: 35

**Required Fields**: None (all fields are optional)

#### Field Reference

| Field Name | Type | Example |
|------------|------|---------|
| `attachments` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `chains` | boolean | true / false |
| `commentsActions` | string (format: html) | "<p>Details here</p>" |
| `contractorName` | string (format: tip) (max length: 32766) | "object/ref123" |
| `customerClient` | string (format: tip) | "object/ref123" |
| `date` | string (format: date) | "2025-01-04" |
| `driver` | boolean | true / false |
| `driverLoaderName` | string (format: tip) (max length: 32766) | "object/ref123" |
| `freeTextWhyIsTheLoadNotCompliant` | string (format: tip) (max length: 32766) | "object/ref123" |
| `goldstarOrContactorList` | string (format: tip) | "contact/user456" |
| `inspectedBy` | string (format: tip) (max length: 32766) | "object/ref123" |
| `isYourLoadCompliantWithTheLoadRestraintGuide2004No` | boolean | true / false |
| `isYourLoadCompliantWithTheLoadRestraintGuide2004Ye` | boolean | true / false |
| `jobNumber` | string (format: tip) (max length: 32766) | "object/ref123" |
| `lcdInspectionId` | string (format: tip) (max length: 32766) | "object/ref123" |
| `loader` | boolean | true / false |
| `loaderPhotoAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `mass` | string (format: tip) (max length: 32766) | "object/ref123" |
| `noOfChains` | number | 5 |
| `noOfStraps` | number | 5 |
| `runNumber` | string (format: tip) (max length: 32766) | "object/ref123" |
| `straps` | boolean | true / false |
| `team` | string (format: tip) | "team/logistics" |
| `totalLoadMassTrailer1` | string (format: tip) (max length: 32766) | "object/ref123" |
| `totalLoadMassTrailer2` | string (format: tip) (max length: 32766) | "object/ref123" |
| `totalLoadMassTrailer3` | string (format: tip) (max length: 32766) | "object/ref123" |
| `trailer` | string (format: tip) | "object/ref123" |
| `trailer2` | string (format: tip) | "object/ref123" |
| `trailer3` | string (format: tip) | "object/ref123" |
| `trailerId` | string (format: tip) (max length: 32766) | "object/ref123" |
| `trailerId2` | string (format: tip) (max length: 32766) | "object/ref123" |
| `trailerId3` | string (format: tip) (max length: 32766) | "object/ref123" |
| `vehicle` | string (format: tip) | "vehicle/abc123" |
| `vehicleId` | string (format: tip) (max length: 32766) | "vehicle/abc123" |
| `whichDepartmentDoesTheLoadBelongTo` | string (format: tip) | "object/ref123" |

### Forklift Prestart Inspection

**Schema Key**: `ObjectType_forkliftPrestartInspection`

**Total Fields**: 92

**Required Fields**: None (all fields are optional)

#### Field Reference

| Field Name | Type | Example |
|------------|------|---------|
| `airCleanerAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `airCleanerComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `airCleanerCompliant` | boolean | true / false |
| `airCleanerDefect` | boolean | true / false |
| `assetId` | string (format: tip) (max length: 32766) | "object/ref123" |
| `assetName` | string (format: tip) (max length: 32766) | "object/ref123" |
| `assetType` | string (format: tip) | "object/ref123" |
| `attachmentComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `attachments` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `attachmentsAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `attachmentsCompliant` | boolean | true / false |
| `attachmentsDefect` | boolean | true / false |
| `audibleAlarmsAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `audibleAlarmsComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `audibleAlarmsCompliant` | boolean | true / false |
| `audibleAlarmsDefect` | boolean | true / false |
| `brakesAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `brakesComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `brakesCompliant` | boolean | true / false |
| `brakesDefect` | boolean | true / false |
| `capacityRatingPlateWarningLabelsAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `capacityRatingPlateWarningLabelsComment` | string (format: tip) (max length: 32766) | "object/ref123" |
| `capacityRatingPlateWarningLabelsCompliant` | boolean | true / false |
| `capacityRatingPlateWarningLabelsDefect` | boolean | true / false |
| `chainHosesCablesAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `chainsHosesCablesComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `chainsHosesCablesCompliant` | boolean | true / false |
| `chainsHosesCablesDefect` | boolean | true / false |
| `comments` | string (format: html) | "<p>Details here</p>" |
| `damageAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `damageComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `damageCompliant` | boolean | true / false |
| `damageDefect` | boolean | true / false |
| `date` | string (format: date) | "2025-01-04" |
| `fluidLeaksComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `fluidLeaksCompliant` | boolean | true / false |
| `fluidLeaksDefect` | boolean | true / false |
| `fluidLevelChecksAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `fluidLevelChecksComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `fluidLevelChecksCompliant` | boolean | true / false |
| `fluidLevelChecksDefect` | boolean | true / false |
| `forkTynesAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `forkTynesComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `forkTynesCompliant` | boolean | true / false |
| `forkTynesDefect` | boolean | true / false |
| `forkliftPrestartInspectionId` | string (format: tip) (max length: 32766) | "object/ref123" |
| `fuelLeaksAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `goldstarAsset` | string (format: tip) | "object/ref123" |
| `guardsAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `guardsComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `guardsCompliant` | boolean | true / false |
| `guardsDefect` | boolean | true / false |
| `hourReadingAtStartOfShift` | string (format: tip) (max length: 32766) | "object/ref123" |
| `hydraulicControlsAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `hydraulicControlsComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `hydraulicControlsCompliant` | boolean | true / false |
| `hydraulicControlsDefect` | boolean | true / false |
| `inchingPedalAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `inchingPedalComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `inchingPedalCompliant` | boolean | true / false |
| `inchingPedalDefect` | boolean | true / false |
| `interlockSpeedGovernorAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `interlockSpeedGovernorComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `interlockSpeedGovernorCompliant` | boolean | true / false |
| `interlockSpeedGovernorDefect` | boolean | true / false |
| `lpgAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `lpgComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `lpgCompliant` | boolean | true / false |
| `lpgDefect` | boolean | true / false |
| `personsCompleting` | string (format: tip) (max length: 32766) | "contact/user456" |
| `preStartStatus` | string (format: tip) | "object/ref123" |
| `radiatorFanAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `radiatorFanComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `radiatorFanCompliant` | boolean | true / false |
| `radiatorFanDefect` | boolean | true / false |
| `safetyDevicesAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `safetyDevicesComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `safetyDevicesCompliant` | boolean | true / false |
| `safetyDevicesDefect` | boolean | true / false |
| `steeringAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `steeringComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `steeringCompliant` | boolean | true / false |
| `steeringDefect` | boolean | true / false |
| `team` | string (format: tip) | "team/logistics" |
| `transmissionFluidLevelsAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `transmissionFluidLevelsComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `transmissionFluidLevelsCompliant` | boolean | true / false |
| `transmissionFluidLevelsDefect` | boolean | true / false |
| `tyreWheelAttachment` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `tyreWheelsComments` | string (format: tip) (max length: 32766) | "object/ref123" |
| `tyreWheelsDefect` | boolean | true / false |
| `tyresWheelsCompliant` | boolean | true / false |

### Coupling Compliance Check

**Schema Key**: `ObjectType_couplingComplianceCheck`

**Total Fields**: 51

**Required Fields**: None (all fields are optional)

#### Field Reference

| Field Name | Type | Example |
|------------|------|---------|
| `checkboxForTrailer2` | boolean | true / false |
| `checkboxForTrailer3` | boolean | true / false |
| `contactBetweenTheSkidPlateTurntablePT1` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `contactBetweenTheSkidPlateTurntablePT2` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `contactBetweenTheSkidPlateTurntablePT3` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `contactBetweenTheSkidPlateTurntableYT1` | boolean | true / false |
| `contactBetweenTheSkidPlateTurntableYT2` | boolean | true / false |
| `contactBetweenTheSkidPlateTurntableYT3` | boolean | true / false |
| `couplingId` | string (format: tip) (max length: 32766) | "object/ref123" |
| `customerClient` | string (format: tip) | "object/ref123" |
| `date` | string (format: date) | "2025-01-04" |
| `goldstarAsset` | string (format: tip) | "object/ref123" |
| `hasATugTestBeenPerformedYT1` | boolean | true / false |
| `hasATugTestBeenPerformedYT2` | boolean | true / false |
| `hasATugTestBeenPerformedYT3` | boolean | true / false |
| `haveTheTrailerLegsBeenRaisedPT1` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `haveTheTrailerLegsBeenRaisedPT2` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `haveTheTrailerLegsBeenRaisedPT3` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `haveTheTrailerLegsBeenRaisedYT1` | boolean | true / false |
| `haveTheTrailerLegsBeenRaisedYT2` | boolean | true / false |
| `haveTheTrailerLegsBeenRaisedYT3` | boolean | true / false |
| `howManyTugTestsPerformedT1` | number | 42.5 |
| `howManyTugTestsPerformedT2` | number | 42.5 |
| `howManyTugTestsPerformedT3` | number | 42.5 |
| `isTheKingPinFullyEngagedPT1` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `isTheKingPinFullyEngagedPT2` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `isTheKingPinFullyEngagedPT3` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `isTheKingPinFullyEngagedYT1` | boolean | true / false |
| `isTheKingPinFullyEngagedYT2` | boolean | true / false |
| `isTheKingPinFullyEngagedYT3` | boolean | true / false |
| `isTheRingFeederPinFullyEngagedAndLockedIntoPlacePT` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `isTheRingFeederPinFullyEngagedAndLockedIntoPlacePT3` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `isTheRingFeederPinFullyEngagedAndLockedIntoPlaceYT` | boolean | true / false |
| `isTheRingFeederPinFullyEngagedAndLockedIntoPlaceYT3` | boolean | true / false |
| `isTheTurntableReleaseHandleFullyEngagedAndTheSafetPT2` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `isTheTurntableReleaseHandleFullyEngagedAndTheSafetYT2` | boolean | true / false |
| `jobNumber` | string (format: tip) (max length: 32766) | "object/ref123" |
| `personCompleting` | string (format: tip) (max length: 32766) | "contact/user456" |
| `runNumber` | string (format: tip) (max length: 32766) | "object/ref123" |
| `team` | string (format: tip) | "team/logistics" |
| `trailer` | string (format: tip) | "object/ref123" |
| `trailer2` | string (format: tip) | "object/ref123" |
| `trailer3` | string (format: tip) | "object/ref123" |
| `trailerId` | string (format: tip) (max length: 32766) | "object/ref123" |
| `trailerId2` | string (format: tip) (max length: 32766) | "object/ref123" |
| `trailerId3` | string (format: tip) (max length: 32766) | "object/ref123" |
| `turntableReleaseHandleFullyEngagedAndTheSafetyChaiPT1` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `turntableReleaseHandleFullyEngagedAndTheSafetyChaiPT3` | array of string (format: tip) (max items: 1000000) | ["object/ref1", "object/ref2"] |
| `turntableReleaseHandleFullyEngagedAndTheSafetyChaiT3` | boolean | true / false |
| `turntableReleaseHandleFullyEngagedAndTheSafetyChaiYT1` | boolean | true / false |
| `vehicleId` | string (format: tip) (max length: 32766) | "vehicle/abc123" |

## Fields by Category

This section organizes fields across all object types by their functional category.

### Identification

#### Coupling Compliance Check

| Field Name | Type |
|------------|------|
| `contactBetweenTheSkidPlateTurntablePT1` | array of string (format: tip) (max items: 1000000) |
| `contactBetweenTheSkidPlateTurntablePT2` | array of string (format: tip) (max items: 1000000) |
| `contactBetweenTheSkidPlateTurntablePT3` | array of string (format: tip) (max items: 1000000) |
| `contactBetweenTheSkidPlateTurntableYT1` | boolean |
| `contactBetweenTheSkidPlateTurntableYT2` | boolean |
| `contactBetweenTheSkidPlateTurntableYT3` | boolean |
| `couplingId` | string (format: tip) (max length: 32766) |
| `jobNumber` | string (format: tip) (max length: 32766) |
| `runNumber` | string (format: tip) (max length: 32766) |
| `trailerId` | string (format: tip) (max length: 32766) |
| `trailerId2` | string (format: tip) (max length: 32766) |
| `trailerId3` | string (format: tip) (max length: 32766) |
| `vehicleId` | string (format: tip) (max length: 32766) |

#### Forklift Prestart Inspection

| Field Name | Type |
|------------|------|
| `assetId` | string (format: tip) (max length: 32766) |
| `fluidLeaksComments` | string (format: tip) (max length: 32766) |
| `fluidLeaksCompliant` | boolean |
| `fluidLeaksDefect` | boolean |
| `fluidLevelChecksAttachment` | array of string (format: tip) (max items: 1000000) |
| `fluidLevelChecksComments` | string (format: tip) (max length: 32766) |
| `fluidLevelChecksCompliant` | boolean |
| `fluidLevelChecksDefect` | boolean |
| `forkliftPrestartInspectionId` | string (format: tip) (max length: 32766) |
| `transmissionFluidLevelsAttachment` | array of string (format: tip) (max items: 1000000) |
| `transmissionFluidLevelsComments` | string (format: tip) (max length: 32766) |
| `transmissionFluidLevelsCompliant` | boolean |
| `transmissionFluidLevelsDefect` | boolean |

#### Load Compliance Check (Driver/Loader)

| Field Name | Type |
|------------|------|
| `isYourLoadCompliantWithTheLoadRestraintGuide2004No` | boolean |
| `isYourLoadCompliantWithTheLoadRestraintGuide2004Ye` | boolean |
| `jobNumber` | string (format: tip) (max length: 32766) |
| `lcdInspectionId` | string (format: tip) (max length: 32766) |
| `runNumber` | string (format: tip) (max length: 32766) |
| `trailerId` | string (format: tip) (max length: 32766) |
| `trailerId2` | string (format: tip) (max length: 32766) |
| `trailerId3` | string (format: tip) (max length: 32766) |
| `vehicleId` | string (format: tip) (max length: 32766) |

#### Load Compliance Check (Supervisor/Manager)

| Field Name | Type |
|------------|------|
| `allPalletsSkidsOrFramesAreInGoodConditionAndAbleToN` | boolean |
| `allPalletsSkidsOrFramesAreInGoodConditionAndAbleToNA` | boolean |
| `allPalletsSkidsOrFramesAreInGoodConditionAndAbleToY` | boolean |
| `allPalletsSkidsOrFramesText` | string (format: tip) (max length: 32766) |
| `isTheLoadCompliantWithTheLoadRestraintGuideN` | boolean |
| `isTheLoadCompliantWithTheLoadRestraintGuideY` | boolean |
| `jobNumber` | string (format: tip) (max length: 32766) |
| `lcsInspectionId` | string (format: tip) (max length: 32766) |
| `numberOfLashingsText` | string (format: tip) (max length: 32766) |
| `numberOfLashingsUsedAppropriateForTheLoadN` | boolean |
| `numberOfLashingsUsedAppropriateForTheLoadNa` | boolean |
| `numberOfLashingsUsedAppropriateForTheLoadY` | boolean |
| `runNumber` | string (format: tip) (max length: 32766) |
| `tailgatesSideAndCentrePinsAreSecuredToTheTrailerEGN` | boolean |
| `tailgatesSideAndCentrePinsAreSecuredToTheTrailerEGNA` | boolean |
| `tailgatesSideAndCentrePinsAreSecuredToTheTrailerEGY` | boolean |
| `tailgatesSideAndCentreText` | string (format: tip) (max length: 32766) |
| `trailerId` | string (format: tip) (max length: 32766) |
| `trailerId2` | string (format: tip) (max length: 32766) |
| `trailerId3` | string (format: tip) (max length: 32766) |
| `vehicleId` | string (format: tip) (max length: 32766) |

#### Site Observations

| Field Name | Type |
|------------|------|
| `siteObservationId` | string (format: tip) (max length: 32766) |

#### Trailer Audits

| Field Name | Type |
|------------|------|
| `trailerAuditId` | string (format: tip) (max length: 32766) |

### Date & Time

#### Coupling Compliance Check

| Field Name | Type |
|------------|------|
| `date` | string (format: date) |

#### Forklift Prestart Inspection

| Field Name | Type |
|------------|------|
| `date` | string (format: date) |

#### Load Compliance Check (Driver/Loader)

| Field Name | Type |
|------------|------|
| `date` | string (format: date) |

#### Load Compliance Check (Supervisor/Manager)

| Field Name | Type |
|------------|------|
| `date` | string (format: date) |

#### Site Observations

| Field Name | Type |
|------------|------|
| `date` | string (format: date) |

#### Trailer Audits

| Field Name | Type |
|------------|------|
| `date` | string (format: date) |

### Personnel

#### Coupling Compliance Check

| Field Name | Type |
|------------|------|
| `personCompleting` | string (format: tip) (max length: 32766) |

#### Forklift Prestart Inspection

| Field Name | Type |
|------------|------|
| `assetName` | string (format: tip) (max length: 32766) |
| `personsCompleting` | string (format: tip) (max length: 32766) |

#### Load Compliance Check (Driver/Loader)

| Field Name | Type |
|------------|------|
| `contractorName` | string (format: tip) (max length: 32766) |
| `driver` | boolean |
| `driverLoaderName` | string (format: tip) (max length: 32766) |
| `goldstarOrContactorList` | string (format: tip) |
| `inspectedBy` | string (format: tip) (max length: 32766) |

#### Load Compliance Check (Supervisor/Manager)

| Field Name | Type |
|------------|------|
| `contractorName` | string (format: tip) (max length: 32766) |
| `driverLoaderName` | string (format: tip) (max length: 32766) |
| `goldstarOrContactorList` | string (format: tip) |
| `inspectedBy` | string (format: tip) (max length: 32766) |
| `loadDoesNotExceedHeadboardHeightByMoreThanHalfTheT` | boolean |
| `loadDoesNotExceedHeadboardHeightByMoreThanHalfTheTN` | boolean |
| `loadDoesNotExceedHeadboardHeightByMoreThanHalfTheTNA` | boolean |

#### Site Observations

| Field Name | Type |
|------------|------|
| `inspectedBy` | string (format: tip) |
| `personInvolved` | array of string (format: tip) (max items: 1000000) |

#### Trailer Audits

| Field Name | Type |
|------------|------|
| `driverComment` | string (format: html) |
| `driverPresentNo` | boolean |
| `driverPresentYes` | boolean |
| `inspectedBy` | string (format: tip) (max length: 32766) |
| `regularDriver` | string (format: tip) |

### Assets & Vehicles

#### Coupling Compliance Check

| Field Name | Type |
|------------|------|
| `checkboxForTrailer2` | boolean |
| `checkboxForTrailer3` | boolean |
| `goldstarAsset` | string (format: tip) |
| `haveTheTrailerLegsBeenRaisedPT1` | array of string (format: tip) (max items: 1000000) |
| `haveTheTrailerLegsBeenRaisedPT2` | array of string (format: tip) (max items: 1000000) |
| `haveTheTrailerLegsBeenRaisedPT3` | array of string (format: tip) (max items: 1000000) |
| `haveTheTrailerLegsBeenRaisedYT1` | boolean |
| `haveTheTrailerLegsBeenRaisedYT2` | boolean |
| `haveTheTrailerLegsBeenRaisedYT3` | boolean |
| `trailer` | string (format: tip) |
| `trailer2` | string (format: tip) |
| `trailer3` | string (format: tip) |

#### Forklift Prestart Inspection

| Field Name | Type |
|------------|------|
| `assetType` | string (format: tip) |
| `goldstarAsset` | string (format: tip) |

#### Load Compliance Check (Driver/Loader)

| Field Name | Type |
|------------|------|
| `totalLoadMassTrailer1` | string (format: tip) (max length: 32766) |
| `totalLoadMassTrailer2` | string (format: tip) (max length: 32766) |
| `totalLoadMassTrailer3` | string (format: tip) (max length: 32766) |
| `trailer` | string (format: tip) |
| `trailer2` | string (format: tip) |
| `trailer3` | string (format: tip) |
| `vehicle` | string (format: tip) |

#### Load Compliance Check (Supervisor/Manager)

| Field Name | Type |
|------------|------|
| `allLashingsAreAnchoredSecurelyToTheTrailerIEHooksNA` | boolean |
| `allLashingsAreAnchoredSecurelyToTheTrailerIEHooksNN` | boolean |
| `allLashingsAreAnchoredSecurelyToTheTrailerIEHooksNY` | boolean |
| `loadDistributedCorrectlyOverTheVehicleAxlesN` | boolean |
| `loadDistributedCorrectlyOverTheVehicleAxlesNa` | boolean |
| `loadDistributedCorrectlyOverTheVehicleAxlesY` | boolean |
| `trailer` | string (format: tip) |
| `trailer2` | string (format: tip) |
| `trailer3` | string (format: tip) |
| `vehicle` | string (format: tip) |
| `vehicleIsAppropriateForTheTaskIEMeetsMassDimension` | boolean |
| `vehicleIsAppropriateForTheTaskIEMeetsMassDimensionN` | boolean |
| `vehicleIsAppropriateForTheTaskIEMeetsMassDimensionNA` | boolean |
| `vehicleIsAppropriateForTheTaskText` | string (format: tip) (max length: 32766) |

#### Site Observations

| Field Name | Type |
|------------|------|
| `vehicleS` | array of string (format: tip) (max items: 1000000) |

#### Trailer Audits

| Field Name | Type |
|------------|------|
| `rego` | string (format: tip) (max length: 32766) |
| `vehicle` | string (format: tip) |

### Organization

#### Coupling Compliance Check

| Field Name | Type |
|------------|------|
| `customerClient` | string (format: tip) |
| `team` | string (format: tip) |

#### Forklift Prestart Inspection

| Field Name | Type |
|------------|------|
| `team` | string (format: tip) |

#### Load Compliance Check (Driver/Loader)

| Field Name | Type |
|------------|------|
| `customerClient` | string (format: tip) |
| `team` | string (format: tip) |
| `whichDepartmentDoesTheLoadBelongTo` | string (format: tip) |

#### Load Compliance Check (Supervisor/Manager)

| Field Name | Type |
|------------|------|
| `customerClient` | string (format: tip) |
| `team` | string (format: tip) |
| `whichDepartmentDoesTheLoadBelongTo` | string (format: tip) |

#### Site Observations

| Field Name | Type |
|------------|------|
| `department` | string (format: tip) |

#### Trailer Audits

| Field Name | Type |
|------------|------|
| `team` | string (format: tip) |

### Checklist Items

#### Coupling Compliance Check

| Field Name | Type |
|------------|------|
| `hasATugTestBeenPerformedYT1` | boolean |
| `hasATugTestBeenPerformedYT2` | boolean |
| `hasATugTestBeenPerformedYT3` | boolean |
| `isTheKingPinFullyEngagedYT1` | boolean |
| `isTheKingPinFullyEngagedYT2` | boolean |
| `isTheKingPinFullyEngagedYT3` | boolean |
| `isTheRingFeederPinFullyEngagedAndLockedIntoPlaceYT` | boolean |
| `isTheRingFeederPinFullyEngagedAndLockedIntoPlaceYT3` | boolean |
| `isTheTurntableReleaseHandleFullyEngagedAndTheSafetYT2` | boolean |
| `turntableReleaseHandleFullyEngagedAndTheSafetyChaiT3` | boolean |
| `turntableReleaseHandleFullyEngagedAndTheSafetyChaiYT1` | boolean |

#### Forklift Prestart Inspection

| Field Name | Type |
|------------|------|
| `airCleanerCompliant` | boolean |
| `airCleanerDefect` | boolean |
| `attachmentsCompliant` | boolean |
| `attachmentsDefect` | boolean |
| `audibleAlarmsCompliant` | boolean |
| `audibleAlarmsDefect` | boolean |
| `brakesCompliant` | boolean |
| `brakesDefect` | boolean |
| `capacityRatingPlateWarningLabelsCompliant` | boolean |
| `capacityRatingPlateWarningLabelsDefect` | boolean |
| `chainsHosesCablesCompliant` | boolean |
| `chainsHosesCablesDefect` | boolean |
| `damageCompliant` | boolean |
| `damageDefect` | boolean |
| `forkTynesCompliant` | boolean |
| `forkTynesDefect` | boolean |
| `guardsCompliant` | boolean |
| `guardsDefect` | boolean |
| `hydraulicControlsCompliant` | boolean |
| `hydraulicControlsDefect` | boolean |
| `inchingPedalCompliant` | boolean |
| `inchingPedalDefect` | boolean |
| `interlockSpeedGovernorCompliant` | boolean |
| `interlockSpeedGovernorDefect` | boolean |
| `lpgCompliant` | boolean |
| `lpgDefect` | boolean |
| `radiatorFanCompliant` | boolean |
| `radiatorFanDefect` | boolean |
| `safetyDevicesCompliant` | boolean |
| `safetyDevicesDefect` | boolean |
| `steeringCompliant` | boolean |
| `steeringDefect` | boolean |
| `tyreWheelsDefect` | boolean |
| `tyresWheelsCompliant` | boolean |

#### Load Compliance Check (Driver/Loader)

| Field Name | Type |
|------------|------|
| `chains` | boolean |
| `loader` | boolean |
| `straps` | boolean |

#### Load Compliance Check (Supervisor/Manager)

| Field Name | Type |
|------------|------|
| `additionalRestraintUsedForItemsThatCanBeDislodgedF` | boolean |
| `additionalRestraintUsedForItemsThatCanBeDislodgedFN` | boolean |
| `additionalRestraintUsedForItemsThatCanBeDislodgedFNA` | boolean |
| `allLashingsPositionedInLineWithDunnageAndBearersFoN` | boolean |
| `allLashingsPositionedInLineWithDunnageAndBearersFoNA` | boolean |
| `allLashingsPositionedInLineWithDunnageAndBearersFoY` | boolean |
| `appropriateStrapAndOrProductProtectionIsInPlaceEGEN` | boolean |
| `appropriateStrapAndOrProductProtectionIsInPlaceEGENA` | boolean |
| `appropriateStrapAndOrProductProtectionIsInPlaceEGEY` | boolean |
| `chains` | boolean |
| `dangerousGoodsLoadsHaveGatesInPlaceNA` | boolean |
| `dangerousGoodsLoadsHaveGatesInPlaceNo` | boolean |
| `dangerousGoodsLoadsHaveGatesInPlaceYes` | boolean |
| `dunnageIsAlignedWithSufficientClampDownForceToKeepN` | boolean |
| `dunnageIsAlignedWithSufficientClampDownForceToKeepNA` | boolean |
| `dunnageIsAlignedWithSufficientClampDownForceToKeepY` | boolean |
| `gluts` | boolean |
| `haveGalasCornersBeenAppliedToCoilsN` | boolean |
| `haveGalasCornersBeenAppliedToCoilsNa` | boolean |
| `haveGalasCornersBeenAppliedToCoilsY` | boolean |
| `loadAreEitherSittingOnTimberRubberOrAntiSlipMateri` | boolean |
| `loadAreEitherSittingOnTimberRubberOrAntiSlipMateriN` | boolean |
| `loadAreEitherSittingOnTimberRubberOrAntiSlipMateriNA` | boolean |
| `loadDoesNotExceedMassOrDimensionOverhangRequiremen` | boolean |
| `loadDoesNotExceedMassOrDimensionOverhangRequiremenNA` | boolean |
| `loadDoesNotExceedMassOrDimensionOverhangRequiremenY` | boolean |
| `loadsAreNotToBeRestrainedAtLowLashingAngle30N` | boolean |
| `loadsAreNotToBeRestrainedAtLowLashingAngle30Na` | boolean |
| `loadsAreNotToBeRestrainedAtLowLashingAngle30Y` | boolean |
| `noLooseItemsEGDunnageChainsStrapsEtcAreLeftOnTheLo` | boolean |
| `noLooseItemsEGDunnageChainsStrapsEtcAreLeftOnTheLoN` | boolean |
| `noLooseItemsEGDunnageChainsStrapsEtcAreLeftOnTheLoNA` | boolean |
| `noRectangularDunnageOnTheShortEdgeNA` | boolean |
| `noRectangularDunnageOnTheShortEdgeNo` | boolean |
| `noRectangularDunnageOnTheShortEdgeYes` | boolean |
| `palletJacksAreParkedAndSecuredNA` | boolean |
| `palletJacksAreParkedAndSecuredNo` | boolean |
| `palletJacksAreParkedAndSecuredYes` | boolean |
| `productProtectionIsInPlaceToPreventScratchesAndProN` | boolean |
| `productProtectionIsInPlaceToPreventScratchesAndProNA` | boolean |
| `productProtectionIsInPlaceToPreventScratchesAndProY` | boolean |
| `restraintEquipmentInGoodWorkingConditionChainsTenNA` | boolean |
| `restraintEquipmentInGoodWorkingConditionChainsTensN` | boolean |
| `restraintEquipmentInGoodWorkingConditionChainsTensY` | boolean |
| `straps` | boolean |
| `toolDuunageBoxesRacksSecuredNA` | boolean |
| `toolDuunageBoxesRacksSecuredNo` | boolean |
| `toolDuunageBoxesRacksSecuredYes` | boolean |
| `webbings` | boolean |

#### Site Observations

| Field Name | Type |
|------------|------|
| `observation1Checkbox` | boolean |
| `observation2Checkbox` | boolean |
| `observation3Checkbox` | boolean |
| `observation4Checkbox` | boolean |

#### Trailer Audits

| Field Name | Type |
|------------|------|
| `externallyExcellent` | boolean |
| `externallyFair` | boolean |
| `externallyGood` | boolean |
| `externallyUnacceptable` | boolean |
| `fireExtinguisherNA` | boolean |
| `fireExtinguisherNo` | boolean |
| `fireExtinguisherYes` | boolean |
| `internallyToolboxExcellent` | boolean |
| `internallyToolboxFair` | boolean |
| `internallyToolboxGood` | boolean |
| `internallyToolboxUnacceptable` | boolean |
| `loadRestraintEquipmentNA` | boolean |
| `loadRestraintEquipmentNo` | boolean |
| `loadRestraintEquipmentYes` | boolean |
| `revolvingBeaconNA` | boolean |
| `revolvingBeaconNo` | boolean |
| `revolvingBeaconYes` | boolean |
| `spareTyreNA` | boolean |
| `spareTyreNo` | boolean |
| `spareTyreYes` | boolean |

### Comments & Notes

#### Forklift Prestart Inspection

| Field Name | Type |
|------------|------|
| `airCleanerComments` | string (format: tip) (max length: 32766) |
| `attachmentComments` | string (format: tip) (max length: 32766) |
| `audibleAlarmsComments` | string (format: tip) (max length: 32766) |
| `brakesComments` | string (format: tip) (max length: 32766) |
| `capacityRatingPlateWarningLabelsComment` | string (format: tip) (max length: 32766) |
| `chainsHosesCablesComments` | string (format: tip) (max length: 32766) |
| `comments` | string (format: html) |
| `damageComments` | string (format: tip) (max length: 32766) |
| `forkTynesComments` | string (format: tip) (max length: 32766) |
| `guardsComments` | string (format: tip) (max length: 32766) |
| `hydraulicControlsComments` | string (format: tip) (max length: 32766) |
| `inchingPedalComments` | string (format: tip) (max length: 32766) |
| `interlockSpeedGovernorComments` | string (format: tip) (max length: 32766) |
| `lpgComments` | string (format: tip) (max length: 32766) |
| `radiatorFanComments` | string (format: tip) (max length: 32766) |
| `safetyDevicesComments` | string (format: tip) (max length: 32766) |
| `steeringComments` | string (format: tip) (max length: 32766) |
| `tyreWheelsComments` | string (format: tip) (max length: 32766) |

#### Load Compliance Check (Driver/Loader)

| Field Name | Type |
|------------|------|
| `commentsActions` | string (format: html) |
| `freeTextWhyIsTheLoadNotCompliant` | string (format: tip) (max length: 32766) |

#### Load Compliance Check (Supervisor/Manager)

| Field Name | Type |
|------------|------|
| `additionalRestraintUsedForItemsText` | string (format: tip) (max length: 32766) |
| `allLashingsAreAnchoredText` | string (format: tip) (max length: 32766) |
| `allLashingsPositionedText` | string (format: tip) (max length: 32766) |
| `appropriateStrapAndOrProductText` | string (format: tip) (max length: 32766) |
| `commentsActions` | string (format: html) |
| `dangerousGoodsLoadsText` | string (format: tip) (max length: 32766) |
| `dunnageIsAlignedText` | string (format: tip) (max length: 32766) |
| `freeTextWhyIsTheLoadNotCompliant` | string (format: tip) (max length: 32766) |
| `haveGalasCornersBeenAppliedToCoilsText` | string (format: tip) (max length: 32766) |
| `loadAreEitherSittingText` | string (format: tip) (max length: 32766) |
| `loadDistributedCorrectlyText` | string (format: tip) (max length: 32766) |
| `loadDoesNotExceedHeadboardText` | string (format: tip) (max length: 32766) |
| `loadDoesNotExceedMassText` | string (format: tip) (max length: 32766) |
| `loadsAreNotToBeRestrainedText` | string (format: tip) (max length: 32766) |
| `noLooseItemsText` | string (format: tip) (max length: 32766) |
| `noRectangularDunnageText` | string (format: tip) (max length: 32766) |
| `palletJacksAreParkedText` | string (format: tip) (max length: 32766) |
| `productProtectionText` | string (format: tip) (max length: 32766) |
| `restraintEquipmentText` | string (format: tip) (max length: 32766) |
| `toolDuunageBoxesText` | string (format: tip) (max length: 32766) |

#### Site Observations

| Field Name | Type |
|------------|------|
| `details1` | string (format: html) |
| `details2` | string (format: html) |
| `details3` | string (format: html) |
| `details4` | string (format: html) |
| `findings1` | string (format: html) |
| `findings2` | string (format: html) |
| `findings3` | string (format: html) |
| `findings4` | string (format: html) |
| `summary1` | string (format: html) |
| `summary2` | string (format: html) |
| `summary3` | string (format: html) |
| `summary4` | string (format: html) |

#### Trailer Audits

| Field Name | Type |
|------------|------|
| `comments` | string (format: html) |

### Attachments

#### Forklift Prestart Inspection

| Field Name | Type |
|------------|------|
| `airCleanerAttachment` | array of string (format: tip) (max items: 1000000) |
| `attachments` | array of string (format: tip) (max items: 1000000) |
| `attachmentsAttachment` | array of string (format: tip) (max items: 1000000) |
| `audibleAlarmsAttachment` | array of string (format: tip) (max items: 1000000) |
| `brakesAttachment` | array of string (format: tip) (max items: 1000000) |
| `capacityRatingPlateWarningLabelsAttachment` | array of string (format: tip) (max items: 1000000) |
| `chainHosesCablesAttachment` | array of string (format: tip) (max items: 1000000) |
| `damageAttachment` | array of string (format: tip) (max items: 1000000) |
| `forkTynesAttachment` | array of string (format: tip) (max items: 1000000) |
| `fuelLeaksAttachment` | array of string (format: tip) (max items: 1000000) |
| `guardsAttachment` | array of string (format: tip) (max items: 1000000) |
| `hydraulicControlsAttachment` | array of string (format: tip) (max items: 1000000) |
| `inchingPedalAttachment` | array of string (format: tip) (max items: 1000000) |
| `interlockSpeedGovernorAttachment` | array of string (format: tip) (max items: 1000000) |
| `lpgAttachment` | array of string (format: tip) (max items: 1000000) |
| `radiatorFanAttachment` | array of string (format: tip) (max items: 1000000) |
| `safetyDevicesAttachment` | array of string (format: tip) (max items: 1000000) |
| `steeringAttachment` | array of string (format: tip) (max items: 1000000) |
| `tyreWheelAttachment` | array of string (format: tip) (max items: 1000000) |

#### Load Compliance Check (Driver/Loader)

| Field Name | Type |
|------------|------|
| `attachments` | array of string (format: tip) (max items: 1000000) |
| `loaderPhotoAttachment` | array of string (format: tip) (max items: 1000000) |

#### Load Compliance Check (Supervisor/Manager)

| Field Name | Type |
|------------|------|
| `attachments` | array of string (format: tip) (max items: 1000000) |
| `signature` | array of string (format: tip) (max items: 1000000) |

#### Site Observations

| Field Name | Type |
|------------|------|
| `attachments1` | array of string (format: tip) (max items: 1000000) |
| `attachments2` | array of string (format: tip) (max items: 1000000) |
| `attachments3` | array of string (format: tip) (max items: 1000000) |
| `attachments4` | array of string (format: tip) (max items: 1000000) |

### Actions

#### Site Observations

| Field Name | Type |
|------------|------|
| `correctiveActions` | array of string (format: tip) (max items: 1000000) |

#### Trailer Audits

| Field Name | Type |
|------------|------|
| `correctiveActions` | array of string (format: tip) (max items: 1000000) |

### Load & Restraint

#### Load Compliance Check (Driver/Loader)

| Field Name | Type |
|------------|------|
| `mass` | string (format: tip) (max length: 32766) |
| `noOfChains` | number |
| `noOfStraps` | number |

#### Load Compliance Check (Supervisor/Manager)

| Field Name | Type |
|------------|------|
| `mass` | string (format: tip) (max length: 32766) |
| `noOfChains` | number |
| `noOfGluts` | number |
| `noOfStraps` | number |
| `noOfWebbings` | number |

#### Trailer Audits

| Field Name | Type |
|------------|------|
| `noOfChains` | number |
| `noOfGluts` | number |
| `noOfWebbingStraps` | number |

### Other

#### Coupling Compliance Check

| Field Name | Type |
|------------|------|
| `howManyTugTestsPerformedT1` | number |
| `howManyTugTestsPerformedT2` | number |
| `howManyTugTestsPerformedT3` | number |
| `isTheKingPinFullyEngagedPT1` | array of string (format: tip) (max items: 1000000) |
| `isTheKingPinFullyEngagedPT2` | array of string (format: tip) (max items: 1000000) |
| `isTheKingPinFullyEngagedPT3` | array of string (format: tip) (max items: 1000000) |
| `isTheRingFeederPinFullyEngagedAndLockedIntoPlacePT` | array of string (format: tip) (max items: 1000000) |
| `isTheRingFeederPinFullyEngagedAndLockedIntoPlacePT3` | array of string (format: tip) (max items: 1000000) |
| `isTheTurntableReleaseHandleFullyEngagedAndTheSafetPT2` | array of string (format: tip) (max items: 1000000) |
| `turntableReleaseHandleFullyEngagedAndTheSafetyChaiPT1` | array of string (format: tip) (max items: 1000000) |
| `turntableReleaseHandleFullyEngagedAndTheSafetyChaiPT3` | array of string (format: tip) (max items: 1000000) |

#### Forklift Prestart Inspection

| Field Name | Type |
|------------|------|
| `hourReadingAtStartOfShift` | string (format: tip) (max length: 32766) |
| `preStartStatus` | string (format: tip) |

#### Site Observations

| Field Name | Type |
|------------|------|
| `siteManager` | string (format: tip) |