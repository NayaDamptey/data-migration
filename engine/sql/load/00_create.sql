USE master;
GO
IF DB_ID(N'RecruitPlatform_Target') IS NOT NULL BEGIN ALTER DATABASE RecruitPlatform_Target SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE RecruitPlatform_Target; END
GO
CREATE DATABASE RecruitPlatform_Target;
GO
ALTER DATABASE RecruitPlatform_Target SET AUTO_CLOSE OFF;
GO
USE RecruitPlatform_Target;
GO
CREATE TABLE dbo.MigrationRejects (
    target_table NVARCHAR(100) NOT NULL,
    source_key NVARCHAR(200) NULL,
    action NVARCHAR(20) NOT NULL,
    reason NVARCHAR(400) NOT NULL,
    logged_at DATETIME2(0) NOT NULL DEFAULT SYSDATETIME()
);
GO
IF OBJECT_ID(N'dbo.User') IS NOT NULL DROP TABLE dbo.[User];
CREATE TABLE dbo.[User] (
    UserID NVARCHAR(50) NOT NULL,
    Loginname NVARCHAR(50),
    ManagerId NVARCHAR(50),
    EnteredDateTime DATETIME,
    UpdatedDateTime DATETIME,
    UserKey NVARCHAR(50),
    Role NVARCHAR(50),
    Email NVARCHAR(50),
    Phone NVARCHAR(50),
    Timezone NVARCHAR(50),
    FullName NVARCHAR(50),
    Status NVARCHAR(50),
    IsDeleted BIT,
    IsArchived BIT
);
GO
IF OBJECT_ID(N'dbo.Company') IS NOT NULL DROP TABLE dbo.Company;
CREATE TABLE dbo.Company (
    ID NVARCHAR(50) NOT NULL,
    CompanyName NVARCHAR(50),
    CompanyType NVARCHAR(50),
    Industry NVARCHAR(50),
    FoundedYear DATE,
    Background NVARCHAR(MAX),
    LocationID NVARCHAR(50),
    Fax NVARCHAR(50),
    Telephone NVARCHAR(50),
    Website NVARCHAR(50),
    Email NVARCHAR(50),
    Type NVARCHAR(50),
    Company_OwnerID NVARCHAR(50),
    AddedBy NVARCHAR(50),
    AddedDate DATETIME,
    UpdatedDate DATETIME,
    Isdeleted BIT,
    IsArchive BIT
);
GO
IF OBJECT_ID(N'dbo.CompanyLocation') IS NOT NULL DROP TABLE dbo.CompanyLocation;
CREATE TABLE dbo.CompanyLocation (
    ID NVARCHAR(50) NOT NULL,
    CompanyID NVARCHAR(50),
    AddressLine1 NVARCHAR(50),
    AddressLine2 NVARCHAR(50),
    AddressLine3 NVARCHAR(50),
    City NVARCHAR(50),
    County NVARCHAR(50),
    PostCode NVARCHAR(50),
    Country NVARCHAR(50),
    AddedAt DATETIME
);
GO
IF OBJECT_ID(N'dbo.Contact') IS NOT NULL DROP TABLE dbo.Contact;
CREATE TABLE dbo.Contact (
    ID NVARCHAR(50) NOT NULL,
    FirstName NVARCHAR(50),
    MiddleName NVARCHAR(50),
    LastName NVARCHAR(50),
    CompanyID NVARCHAR(50),
    Email NVARCHAR(50),
    Phone NVARCHAR(50),
    Fax NVARCHAR(50),
    URL NVARCHAR(50),
    Role NVARCHAR(50),
    Contacttype NVARCHAR(50),
    PositionTitle NVARCHAR(50),
    DepartmentID NVARCHAR(50),
    LocationID NVARCHAR(50),
    IsPrimary BIT,
    Industry NVARCHAR(50),
    ContactOwnerID NVARCHAR(50),
    IsDeleted BIT,
    IsArchived BIT,
    AddedBy NVARCHAR(50),
    ModifiedBy NVARCHAR(50),
    AddedAt DATETIME,
    ModifiedAt DATETIME,
    Notes NVARCHAR(MAX)
);
GO
IF OBJECT_ID(N'dbo.Applicant') IS NOT NULL DROP TABLE dbo.Applicant;
CREATE TABLE dbo.Applicant (
    ApplicantID NVARCHAR(50) NOT NULL,
    FirstName NVARCHAR(50),
    MiddleName NVARCHAR(50),
    LastName NVARCHAR(50),
    ApplicantCommsID INT,
    LocationID NVARCHAR(50),
    Gender NVARCHAR(50),
    DateOfBirth DATE,
    Status NVARCHAR(50),
    EmploymentType NVARCHAR(50),
    JobTitle NVARCHAR(50),
    Department NVARCHAR(50),
    SSN NVARCHAR(50),
    Nationality NVARCHAR(50),
    VisaStatus NVARCHAR(50),
    WillingToRelocate BIT,
    Source NVARCHAR(50),
    ScreeningScore INT,
    Active BIT,
    ApplicantOwner NVARCHAR(50),
    AddedBy NVARCHAR(50),
    UpdatedBy NVARCHAR(50),
    AddedAt DATETIME,
    UpdatedAt DATETIME,
    Deleted BIT
);
GO
IF OBJECT_ID(N'dbo.Comms') IS NOT NULL DROP TABLE dbo.Comms;
CREATE TABLE dbo.Comms (
    ID INT NOT NULL,
    ObjectID NVARCHAR(50),
    ObjectType NVARCHAR(50),
    Value NVARCHAR(50),
    Type NVARCHAR(50),
    Deleted BIT,
    AddedBy NVARCHAR(50),
    UpdatedBy NVARCHAR(50)
);
GO
IF OBJECT_ID(N'dbo.Position') IS NOT NULL DROP TABLE dbo.Position;
CREATE TABLE dbo.Position (
    ID INT NOT NULL,
    PositionName NVARCHAR(50),
    ContactID NVARCHAR(50),
    PositionLocationID NVARCHAR(50),
    PositionDesc NVARCHAR(MAX),
    Status NVARCHAR(50),
    Filled BIT,
    Closed BIT,
    Source NVARCHAR(50),
    PurchaseOrderNo NVARCHAR(50),
    Archived BIT,
    Deleted BIT,
    PositionChargeRate FLOAT,
    PositionPayRate FLOAT,
    Salary NVARCHAR(50),
    Currency NVARCHAR(50),
    DateBegins DATE,
    DateEnds DATE,
    DatePublished DATE,
    DateFilled DATE,
    Addedby NVARCHAR(50),
    Addedat DATETIME,
    PositionOwnerID NVARCHAR(50),
    UpdatedBy NVARCHAR(50),
    UpdatedAt DATETIME,
    CompanyID NVARCHAR(50),
    Duration INT
);
GO
IF OBJECT_ID(N'dbo.Placements') IS NOT NULL DROP TABLE dbo.Placements;
CREATE TABLE dbo.Placements (
    ID INT NOT NULL,
    ApplicantID NVARCHAR(50),
    PositionID INT,
    CompanyID NVARCHAR(50),
    PlacedDate DATE,
    EmploymentType NVARCHAR(50),
    StartDate DATE,
    EndDate DATE,
    Salary INT,
    PayRate FLOAT,
    ChargeRate FLOAT,
    Status NVARCHAR(50),
    ReportsTo NVARCHAR(50),
    WorkShift NVARCHAR(50),
    OnboardingLevel INT,
    Fee FLOAT,
    IsWFH BIT,
    Notes NVARCHAR(MAX),
    EndReason NVARCHAR(MAX),
    OwnerID NVARCHAR(50),
    AddedAt DATETIME,
    AddedBy NVARCHAR(50),
    UpdatedAt DATETIME,
    UpdatedBy NVARCHAR(50)
);
GO
IF OBJECT_ID(N'dbo.Notes') IS NOT NULL DROP TABLE dbo.Notes;
CREATE TABLE dbo.Notes (
    ID INT NOT NULL,
    Text NVARCHAR(MAX),
    ApplicantID NVARCHAR(50),
    CompanyID NVARCHAR(50),
    PositionID INT,
    ContactID NVARCHAR(50),
    Deleted BIT,
    AddedAt DATETIME,
    UserID NVARCHAR(50)
);
GO
IF OBJECT_ID(N'dbo.Task') IS NOT NULL DROP TABLE dbo.Task;
CREATE TABLE dbo.Task (
    ID INT NOT NULL,
    TaskType NVARCHAR(50),
    OwnerUserID NVARCHAR(50),
    Subject NVARCHAR(50),
    Note NVARCHAR(MAX),
    Status NVARCHAR(50),
    Priority INT,
    StartDate DATE,
    Enddate DATE,
    Completed BIT,
    AddedAt DATETIME,
    UpdatedAt DATETIME
);
GO
IF OBJECT_ID(N'dbo.TaskItem') IS NOT NULL DROP TABLE dbo.TaskItem;
CREATE TABLE dbo.TaskItem (
    ID INT NOT NULL,
    TaskID INT,
    ObjectID NVARCHAR(50),
    ObjectType NVARCHAR(50),
    AddedBy NVARCHAR(50),
    UpdatedBy NVARCHAR(50),
    AddedAt DATETIME,
    UpdatedAt DATETIME
);
GO
IF OBJECT_ID(N'dbo.Attachments') IS NOT NULL DROP TABLE dbo.Attachments;
CREATE TABLE dbo.Attachments (
    AttachmentID INT NOT NULL,
    AttachmentType NVARCHAR(50),
    AttachmentName NVARCHAR(50),
    Description NVARCHAR(50),
    FilePath NVARCHAR(50),
    FileType NVARCHAR(50),
    UploadedBy NVARCHAR(50),
    UploadedAt DATETIME,
    IsPrimary BIT,
    IsArchived BIT,
    IsDeleted BIT
);
GO
IF OBJECT_ID(N'dbo.Department') IS NOT NULL DROP TABLE dbo.Department;
CREATE TABLE dbo.Department (
    ID INT NOT NULL,
    Name NVARCHAR(50),
    AddedAt DATETIME,
    UpdatedAt DATETIME
);
GO
IF OBJECT_ID(N'dbo.SkillCategory') IS NOT NULL DROP TABLE dbo.SkillCategory;
CREATE TABLE dbo.SkillCategory (
    ID NVARCHAR(50) NOT NULL,
    CategoryName NVARCHAR(50),
    Deleted BIT
);
GO
IF OBJECT_ID(N'dbo.Skills') IS NOT NULL DROP TABLE dbo.Skills;
CREATE TABLE dbo.Skills (
    ID NVARCHAR(50) NOT NULL,
    SkillName NVARCHAR(50),
    SkillCategoryID NVARCHAR(50),
    Status NVARCHAR(50),
    AddedAt DATETIME,
    AddedBy NVARCHAR(50),
    UpdatedAt DATETIME,
    UpdatedBy NVARCHAR(50)
);
GO
IF OBJECT_ID(N'dbo.PositionType') IS NOT NULL DROP TABLE dbo.PositionType;
CREATE TABLE dbo.PositionType (
    ID INT,
    Type NVARCHAR(50)
);
GO
IF OBJECT_ID(N'dbo.Position_Details') IS NOT NULL DROP TABLE dbo.Position_Details;
CREATE TABLE dbo.Position_Details (
    ID INT NOT NULL,
    PositionID INT,
    Department NVARCHAR(50),
    Requirement NVARCHAR(MAX),
    Qualification NVARCHAR(MAX),
    PositionTypeID INT,
    Location NVARCHAR(50),
    ClosingDate DATE,
    SeniorityLevel NVARCHAR(50),
    PayFrequency NVARCHAR(50),
    AddedBy NVARCHAR(50),
    AddedAt DATETIME,
    UpdatedAt DATETIME,
    UpdatedBy NVARCHAR(50)
);
GO
IF OBJECT_ID(N'dbo.Position_Applicant') IS NOT NULL DROP TABLE dbo.Position_Applicant;
CREATE TABLE dbo.Position_Applicant (
    ID INT NOT NULL,
    PositionID INT,
    ApplicantID NVARCHAR(50),
    CompanyID NVARCHAR(50),
    ApplicationDate DATE,
    StatusTxt NVARCHAR(50),
    InterviewDate DATE,
    Score INT,
    Notes NVARCHAR(MAX),
    AddedBy NVARCHAR(50),
    AddedAt DATETIME,
    UpdatedBy NVARCHAR(50),
    UpdatedAt DATETIME,
    Active BIT,
    NoticePeriod NVARCHAR(50),
    ExpectedSalary DECIMAL(8,2),
    PayRate DECIMAL(8,2),
    ChargeRate DECIMAL(8,2)
);
GO
IF OBJECT_ID(N'dbo.Shortlist') IS NOT NULL DROP TABLE dbo.Shortlist;
CREATE TABLE dbo.Shortlist (
    ID INT NOT NULL,
    PositionID INT,
    ApplicantID NVARCHAR(50),
    ShortlistedDate DATE,
    Status NVARCHAR(50),
    AddedBy NVARCHAR(50),
    AddedAt DATETIME,
    UpdatedAt DATETIME
);
GO
IF OBJECT_ID(N'dbo.Offer') IS NOT NULL DROP TABLE dbo.Offer;
CREATE TABLE dbo.Offer (
    ID INT NOT NULL,
    PlacementID INT,
    Accepted BIT,
    RejectedReason NVARCHAR(50),
    Terms NVARCHAR(50),
    RecruiterID NVARCHAR(50)
);
GO
IF OBJECT_ID(N'dbo.Deal') IS NOT NULL DROP TABLE dbo.Deal;
CREATE TABLE dbo.Deal (
    ID INT NOT NULL,
    PlacementID INT,
    RecruiterID NVARCHAR(50),
    CompanyID NVARCHAR(50),
    DealDate DATE,
    DealType NVARCHAR(50),
    DealValue DECIMAL(8,2),
    InvoiceID INT,
    Notes NVARCHAR(MAX),
    AddedAt DATETIME,
    AddedBy NVARCHAR(50)
);
GO
IF OBJECT_ID(N'dbo.Deal_Stage') IS NOT NULL DROP TABLE dbo.Deal_Stage;
CREATE TABLE dbo.Deal_Stage (
    ID INT NOT NULL,
    DealID INT,
    Stage NVARCHAR(50),
    AddedAt DATETIME,
    UpdatedAt DATETIME
);
GO
IF OBJECT_ID(N'dbo.Work_History') IS NOT NULL DROP TABLE dbo.Work_History;
CREATE TABLE dbo.Work_History (
    ID INT NOT NULL,
    ApplicationID NVARCHAR(50),
    CompanyName NVARCHAR(50),
    PositionTitle NVARCHAR(50),
    EmploymentType NVARCHAR(50),
    StartDate DATE,
    EndDate DATE,
    ReasonForLeaving NVARCHAR(255),
    AddedAt DATETIME,
    UpdatedAt DATETIME
);
GO
IF OBJECT_ID(N'dbo.References') IS NOT NULL DROP TABLE dbo.[References];
CREATE TABLE dbo.[References] (
    ID NVARCHAR(50) NOT NULL,
    ApplicantID NVARCHAR(50),
    Fullname NVARCHAR(50),
    PositionTitle NVARCHAR(50),
    CompanyName NVARCHAR(50),
    Relationship NVARCHAR(50),
    Email NVARCHAR(50),
    PhoneContact NVARCHAR(50),
    ReferenceType NVARCHAR(50),
    Notes NVARCHAR(50),
    VerifiedBy NVARCHAR(50),
    VerifiedAt DATETIME,
    AddedAt DATETIME,
    UpdatedAt DATETIME
);
GO
IF OBJECT_ID(N'dbo.Employment_Details') IS NOT NULL DROP TABLE dbo.Employment_Details;
CREATE TABLE dbo.Employment_Details (
    ID INT NOT NULL,
    Employment_TypeID NVARCHAR(50),
    Employment_Type NVARCHAR(50),
    ApplicantID NVARCHAR(50),
    DesiredPayrate FLOAT,
    CurrentPayrate FLOAT,
    MarketingEmail BIT,
    MarketingPhone BIT,
    MarketingText BIT,
    Bank NVARCHAR(50),
    SortCode NVARCHAR(50),
    AccNo INT,
    Notes NVARCHAR(MAX),
    Industry NVARCHAR(50),
    EmployerName NVARCHAR(50),
    ContactID NVARCHAR(50),
    AddedBy NVARCHAR(50),
    AddedAt DATETIME,
    UpdatedBy NVARCHAR(50),
    UpdatedAt DATETIME
);
GO
IF OBJECT_ID(N'dbo.Marketing') IS NOT NULL DROP TABLE dbo.Marketing;
CREATE TABLE dbo.Marketing (
    ID INT NOT NULL,
    ApplicantID NVARCHAR(50),
    Email NVARCHAR(50),
    Phone NVARCHAR(50),
    Text NVARCHAR(50),
    GDPRConsent BIT,
    OptIn BIT,
    OptOut BIT,
    AddedAt DATETIME,
    UpdatedAt DATETIME,
    AddedBy NVARCHAR(50),
    UpdatedBy NVARCHAR(50)
);
GO
IF OBJECT_ID(N'dbo.Sources') IS NOT NULL DROP TABLE dbo.Sources;
CREATE TABLE dbo.Sources (
    ID NVARCHAR(50),
    Name NVARCHAR(50),
    AddedAt DATETIME
);
GO
IF OBJECT_ID(N'dbo.Currencies') IS NOT NULL DROP TABLE dbo.Currencies;
CREATE TABLE dbo.Currencies (
    CurrencyID INT NOT NULL,
    CurrencyCode NVARCHAR(50)
);
GO
IF OBJECT_ID(N'dbo.Timesheets') IS NOT NULL DROP TABLE dbo.Timesheets;
CREATE TABLE dbo.Timesheets (
    ID INT NOT NULL,
    StartDate DATE,
    EndDate DATE,
    Payrate DECIMAL(8,2),
    ChargeRate DECIMAL(8,2),
    Currency NVARCHAR(50),
    Status NVARCHAR(50),
    TimesheetType NVARCHAR(50),
    TotalWeekHours FLOAT,
    ApprovedBy NVARCHAR(50),
    AddedAt DATETIME,
    UpdatedAt DATETIME,
    Deleted BIT
);
GO
IF OBJECT_ID(N'dbo.TimesheetActivity') IS NOT NULL DROP TABLE dbo.TimesheetActivity;
CREATE TABLE dbo.TimesheetActivity (
    ActivityID INT NOT NULL,
    TimesheetID INT,
    AssocID INT,
    InvoiceID INT,
    TimesheetDate DATE,
    HoursWorked FLOAT,
    ShiftID INT,
    Status NVARCHAR(50),
    AddedBy NVARCHAR(50),
    AddedAt DATETIME,
    UpdatedAt DATETIME
);
GO
IF OBJECT_ID(N'dbo.PurchaseOrder') IS NOT NULL DROP TABLE dbo.PurchaseOrder;
CREATE TABLE dbo.PurchaseOrder (
    PONo NVARCHAR(50) NOT NULL,
    CompanyID NVARCHAR(50),
    PODate DATE,
    POAmount DECIMAL(8,2),
    Status NVARCHAR(50),
    AddedAt DATETIME,
    AddedBy NVARCHAR(50),
    UpdatedAt DATETIME,
    UpdatedBy NVARCHAR(50)
);
GO
IF OBJECT_ID(N'dbo.PurchaseOrderItems') IS NOT NULL DROP TABLE dbo.PurchaseOrderItems;
CREATE TABLE dbo.PurchaseOrderItems (
    ID INT NOT NULL,
    PONo NVARCHAR(50),
    PositionID INT,
    PlacementID INT,
    Description NVARCHAR(255),
    Quantity INT,
    UnitPrice DECIMAL(8,2),
    Amount DECIMAL(8,2),
    Status NVARCHAR(50),
    AddedBy NVARCHAR(50),
    AddedAt DATETIME,
    UpdatedAt DATETIME,
    UpdatedBy NVARCHAR(50)
);
GO
IF OBJECT_ID(N'dbo.Invoice') IS NOT NULL DROP TABLE dbo.Invoice;
CREATE TABLE dbo.Invoice (
    ID INT NOT NULL,
    Type NVARCHAR(50),
    InvoiceNo NVARCHAR(50),
    PlacementID INT,
    DealID INT,
    Amount DECIMAL(8,2),
    TaxAmount DECIMAL(8,2),
    Currency NVARCHAR(50),
    InvoiceDate DATE,
    DueDate DATE,
    PaymentDate DATE,
    Status NVARCHAR(50),
    Notes NVARCHAR(MAX),
    AddedBy NVARCHAR(50),
    UpdatedBy NVARCHAR(50)
);
GO
IF OBJECT_ID(N'dbo.Leads') IS NOT NULL DROP TABLE dbo.Leads;
CREATE TABLE dbo.Leads (
    ID INT NOT NULL,
    Fullname NVARCHAR(50),
    PipelineStage NVARCHAR(50),
    CompanyID NVARCHAR(50),
    Type NVARCHAR(50),
    Skills NVARCHAR(MAX),
    Source NVARCHAR(50),
    CommID INT,
    Notes NVARCHAR(MAX),
    Deleted BIT,
    AddedAt DATETIME,
    AddedBy NVARCHAR(50),
    UpdatedAt DATETIME,
    UpdatedBy NVARCHAR(50)
);
GO
IF OBJECT_ID(N'dbo.ApplicantAttachment') IS NOT NULL DROP TABLE dbo.ApplicantAttachment;
CREATE TABLE dbo.ApplicantAttachment (
    ID INT NOT NULL,
    AttachmentID INT,
    ApplicantID NVARCHAR(50),
    AddedBy NVARCHAR(50),
    AddedAt DATETIME,
    UpdatedAt DATETIME
);
GO
IF OBJECT_ID(N'dbo.ContactAttachment') IS NOT NULL DROP TABLE dbo.ContactAttachment;
CREATE TABLE dbo.ContactAttachment (
    ID INT NOT NULL,
    AttachmentID INT,
    ContactID NVARCHAR(50),
    AddedBy NVARCHAR(50),
    AddedAt DATETIME,
    UpdatedAt DATETIME
);
GO
IF OBJECT_ID(N'dbo.PositionAttachment') IS NOT NULL DROP TABLE dbo.PositionAttachment;
CREATE TABLE dbo.PositionAttachment (
    ID INT NOT NULL,
    AttachmentID INT,
    PositionID INT,
    AddedBy NVARCHAR(50),
    AddedAt DATETIME,
    UpdatedAt DATETIME
);
GO
