CREATE PROCEDURE [store].[spSELECT]
    @ClientName VARCHAR(255) = NULL

AS
SELECT * FROM store.Clients WHERE name = @ClientName
